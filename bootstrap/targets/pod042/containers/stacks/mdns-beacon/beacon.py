#!/usr/bin/env python3
"""Keep devices on Scanners discoverable when they will not answer for themselves.

Once a minute the UDMP's mDNS proxy asks each network for
`_services._dns-sd._udp.local` and then browses only the service types that come
back. The Canon printer answers every direct query but never that one, so the beacon
names the given types on its behalf.

Asleep, the printer ignores multicast altogether. It still answers ARP, ping, TCP
handshakes and even HTTP, and only an IPP request wakes it. Its records then expire
from the proxy, and a Mac on another network cannot resolve the address it would
send that request to. So the beacon asks the printer for its records whenever it
hears it awake, and answers in its place while it sleeps, but only while it still
answers ping: when the printer is off, the proxy browses and finds nothing.
"""

import argparse
from dataclasses import dataclass
import socket
import struct
import time
from typing import cast
import urllib.request

MDNS_GROUP = "224.0.0.251"
MDNS_PORT = 5353
ENUMERATION = "_services._dns-sd._udp.local"
HEADER = struct.Struct("!6H")
QUESTION = struct.Struct("!HH")
RECORD = struct.Struct("!HHIH")
SRV_FIXED_FIELDS = 6
RESPONSE_BIT = 0x8000
AUTHORITATIVE_RESPONSE = 0x8400
CACHE_FLUSH = 0x8000
COMPRESSION_POINTER = 0xC0
A = 1
PTR = 12
TXT = 16
AAAA = 28
SRV = 33
ANY = 255
IN = 1
PROXIED_TYPES = {A, PTR, TXT, AAAA, SRV}
SHARED_RECORD_TTL = 4500
# Short enough that the proxy forgets a printer within two minutes of it going
# silent, long enough to survive between its once-a-minute browses.
PROXY_TTL = 120
LIVENESS_SECONDS = 30
ASK_SECONDS = 60
WAKE_SECONDS = 3
PING_ATTEMPTS = 3
ICMP_ECHO = struct.pack("!BBHHH", 8, 0, 0, 0, 0)
IPP_GET_PRINTER_ATTRIBUTES = 0x000B
IPP_OPERATION_ATTRIBUTES = 0x01
IPP_END_OF_ATTRIBUTES = 0x03
IPP_CHARSET = 0x47
IPP_NATURAL_LANGUAGE = 0x48
IPP_URI = 0x45
IPP_KEYWORD = 0x44


@dataclass(frozen=True)
class Record:
    name: str
    rtype: int
    rclass: int
    # Names inside rdata are expanded so the record can be placed in any packet.
    rdata: bytes


Question = tuple[str, int]
Cache = dict[tuple[str, int], dict[bytes, Record]]


def encode_name(name: str) -> bytes:
    labels = [label.encode() for label in name.split(".")]
    return b"".join(bytes([len(label)]) + label for label in labels) + b"\x00"


def read_name(packet: bytes, offset: int) -> tuple[str, int]:
    """Decode a possibly compressed name, returning it and the offset just past it."""
    labels: list[str] = []
    resume: int | None = None
    while (length := packet[offset]) != 0:
        if length & COMPRESSION_POINTER == COMPRESSION_POINTER:
            target = (length & ~COMPRESSION_POINTER) << 8 | packet[offset + 1]
            if target >= offset:
                raise ValueError("compression pointer does not point backwards")
            resume = resume or offset + 2
            offset = target
            continue
        labels.append(packet[offset + 1 : offset + 1 + length].decode())
        offset += 1 + length
    return ".".join(labels), resume or offset + 1


def parse(packet: bytes) -> tuple[int, list[Question], list[tuple[Record, int]]]:
    """Return a packet's flags, its questions, and its proxiable records with TTLs."""
    _, flags, question_count, *section_counts = HEADER.unpack_from(packet)
    offset = HEADER.size
    questions: list[Question] = []
    for _ in range(question_count):
        name, offset = read_name(packet, offset)
        record_type, _ = QUESTION.unpack_from(packet, offset)
        offset += QUESTION.size
        questions.append((name, record_type))
    records: list[tuple[Record, int]] = []
    for _ in range(sum(section_counts)):
        name, offset = read_name(packet, offset)
        rtype, rclass, ttl, length = RECORD.unpack_from(packet, offset)
        offset += RECORD.size
        rdata = packet[offset : offset + length]
        if rtype == PTR:
            rdata = encode_name(read_name(packet, offset)[0])
        elif rtype == SRV:
            target = read_name(packet, offset + SRV_FIXED_FIELDS)[0]
            rdata = rdata[:SRV_FIXED_FIELDS] + encode_name(target)
        offset += length
        if rtype in PROXIED_TYPES:
            records.append((Record(name, rtype, rclass, rdata), ttl))
    return flags, questions, records


def learn(cache: Cache, records: list[tuple[Record, int]]) -> None:
    """Apply one announcement: cache-flush replaces a set, TTL 0 says goodbye."""
    flushed: set[tuple[str, int]] = set()
    for record, ttl in records:
        key = (record.name.lower(), record.rtype)
        if record.rclass & CACHE_FLUSH and key not in flushed:
            cache[key] = {}
            flushed.add(key)
        known = cache.setdefault(key, {})
        if ttl == 0:
            known.pop(record.rdata, None)
        else:
            known[record.rdata] = record


def lookup(cache: Cache, name: str, rtype: int) -> list[Record]:
    if rtype == ANY:
        return [
            record
            for (known_name, _), known in cache.items()
            if known_name == name.lower()
            for record in known.values()
        ]
    return list(cache.get((name.lower(), rtype), {}).values())


def following(cache: Cache, record: Record) -> list[Record]:
    """The records a resolver asks for next, sent along with it (RFC 6763 section 12)."""
    if record.rtype == PTR:
        instance = read_name(record.rdata, 0)[0]
        return lookup(cache, instance, SRV) + lookup(cache, instance, TXT)
    if record.rtype == SRV:
        host = read_name(record.rdata, SRV_FIXED_FIELDS)[0]
        return lookup(cache, host, A) + lookup(cache, host, AAAA)
    return []


def answers(cache: Cache, question: Question) -> list[Record]:
    records = lookup(cache, *question)
    pending = list(records)
    while pending:
        for record in following(cache, pending.pop()):
            if record not in records:
                records.append(record)
                pending.append(record)
    return records


def response(
    query_id: int, questions: list[Question], records: list[Record], ttl: int
) -> bytes:
    packet = HEADER.pack(
        query_id, AUTHORITATIVE_RESPONSE, len(questions), len(records), 0, 0
    )
    for name, rtype in questions:
        packet += encode_name(name) + QUESTION.pack(rtype, IN)
    for record in records:
        rclass = record.rclass & ~CACHE_FLUSH if questions else record.rclass
        packet += encode_name(record.name)
        packet += RECORD.pack(record.rtype, rclass, ttl, len(record.rdata))
        packet += record.rdata
    return packet


def reply(
    listener: socket.socket,
    query_id: int,
    question: Question,
    records: list[Record],
    ttl: int,
    querier: tuple[str, int],
) -> None:
    # The proxy asks from an ephemeral port, which makes it a legacy querier owed
    # a unicast reply echoing its ID and question, without cache-flush bits (RFC 6762
    # section 6.7). The multicast copy is what the live experiment also sent, and it
    # worked.
    if querier[1] != MDNS_PORT:
        listener.sendto(response(query_id, [question], records, ttl), querier)
    listener.sendto(response(0, [], records, ttl), (MDNS_GROUP, MDNS_PORT))


def answers_ping(address: str) -> bool:
    """Ping without privileges. The printer answers asleep, and stays asleep."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_ICMP) as ping:
        ping.settimeout(1)
        for _ in range(PING_ATTEMPTS):
            try:
                ping.sendto(ICMP_ECHO, (address, 0))
                ping.recv(1500)
                return True
            except OSError:
                continue
    return False


def ipp_attribute(tag: int, name: str, value: str) -> bytes:
    encoded_name, encoded_value = name.encode(), value.encode()
    return (
        struct.pack("!BH", tag, len(encoded_name))
        + encoded_name
        + struct.pack("!H", len(encoded_value))
        + encoded_value
    )


def wake(printer: str) -> None:
    """Ask for the printer's state over IPP, the one request that wakes it."""
    uri = f"ipp://{printer}/ipp/print"
    body = (
        struct.pack(
            "!BBHIB", 2, 0, IPP_GET_PRINTER_ATTRIBUTES, 1, IPP_OPERATION_ATTRIBUTES
        )
        + ipp_attribute(IPP_CHARSET, "attributes-charset", "utf-8")
        + ipp_attribute(IPP_NATURAL_LANGUAGE, "attributes-natural-language", "en")
        + ipp_attribute(IPP_URI, "printer-uri", uri)
        + ipp_attribute(IPP_KEYWORD, "requested-attributes", "printer-state")
        + bytes([IPP_END_OF_ATTRIBUTES])
    )
    request = urllib.request.Request(
        f"http://{printer}:631/ipp/print",
        data=body,
        headers={"Content-Type": "application/ipp"},
    )
    with urllib.request.urlopen(request, timeout=10) as reply:
        reply.read()


def ask(listener: socket.socket, types: list[str]) -> None:
    """Browse every type at once, so one awake moment fills the whole cache."""
    packet = HEADER.pack(0, 0, len(types), 0, 0, 0)
    for service_type in types:
        packet += encode_name(service_type) + QUESTION.pack(PTR, IN)
    listener.sendto(packet, (MDNS_GROUP, MDNS_PORT))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--printer", required=True, metavar="ADDRESS")
    parser.add_argument("types", nargs="+", metavar="SERVICE_TYPE")
    args = parser.parse_args()
    printer: str = args.printer
    enumeration = [
        Record(ENUMERATION, PTR, IN, encode_name(service_type))
        for service_type in args.types
    ]
    listener = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    listener.bind(("", MDNS_PORT))
    membership = socket.inet_aton(MDNS_GROUP) + socket.inet_aton("0.0.0.0")
    listener.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, membership)
    listener.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 255)
    print(f"answering {ENUMERATION} with {' '.join(args.types)}", flush=True)
    print(f"answering for {printer} while it answers ping", flush=True)
    # Nothing is cached yet, and a sleeping printer would not hear the question.
    try:
        wake(printer)
    except OSError as error:
        print(f"could not wake {printer}: {error}", flush=True)
    else:
        time.sleep(WAKE_SECONDS)
        ask(listener, args.types)
    cache: Cache = {}
    alive = False
    checked_at = float("-inf")
    asked_at = time.monotonic()
    while True:
        packet, sender = listener.recvfrom(9000)
        querier = cast(tuple[str, int], sender)
        try:
            flags, questions, records = parse(packet)
        except (IndexError, UnicodeDecodeError, ValueError, struct.error):
            continue
        if flags & RESPONSE_BIT:
            if querier == (printer, MDNS_PORT):
                learn(cache, records)
                if time.monotonic() - asked_at > ASK_SECONDS:
                    ask(listener, args.types)
                    asked_at = time.monotonic()
            continue
        # Its own queries include probes for its names, which an answer would turn
        # into a conflict.
        if querier[0] == printer:
            continue
        query_id = HEADER.unpack_from(packet)[0]
        for question in questions:
            name, rtype = question
            if name.lower() == ENUMERATION and rtype in (PTR, ANY):
                reply(
                    listener,
                    query_id,
                    question,
                    enumeration,
                    SHARED_RECORD_TTL,
                    querier,
                )
                continue
            if not (proxied := answers(cache, question)):
                continue
            if time.monotonic() - checked_at > LIVENESS_SECONDS:
                was_alive, alive = alive, answers_ping(printer)
                checked_at = time.monotonic()
                if alive != was_alive:
                    state = "answers ping" if alive else "stopped answering ping"
                    print(f"{printer} {state}", flush=True)
            if alive:
                reply(listener, query_id, question, proxied, PROXY_TTL, querier)


if __name__ == "__main__":
    main()
