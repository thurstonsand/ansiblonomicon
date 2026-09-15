#!/usr/bin/env python3
"""Answer DNS-SD service type enumeration for devices on Scanners that do not.

Once a minute the UDMP's mDNS proxy asks each network for
`_services._dns-sd._udp.local` and then browses only the service types that come
back. The Canon printer answers every direct query but never that one, so the proxy
never caches its AirPrint and AirScan records and no other network can find it.

This names the given types and nothing else. It publishes no instances, so it cannot
invent a printer: when the real one is off, the proxy browses and finds nothing.
"""

import socket
import struct
import sys
from typing import cast

MDNS_GROUP = "224.0.0.251"
MDNS_PORT = 5353
ENUMERATION = "_services._dns-sd._udp.local"
HEADER = struct.Struct("!6H")
QUESTION = struct.Struct("!HH")
RECORD = struct.Struct("!HHIH")
RESPONSE_BIT = 0x8000
AUTHORITATIVE_RESPONSE = 0x8400
COMPRESSION_POINTER = 0xC0
PTR = 12
ANY = 255
IN = 1
SHARED_RECORD_TTL = 4500


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


def asks_for_enumeration(packet: bytes) -> bool:
    _, flags, questions, _, _, _ = HEADER.unpack_from(packet)
    if flags & RESPONSE_BIT:
        return False
    offset = HEADER.size
    for _ in range(questions):
        name, offset = read_name(packet, offset)
        record_type, _ = QUESTION.unpack_from(packet, offset)
        offset += QUESTION.size
        if name.lower() == ENUMERATION and record_type in (PTR, ANY):
            return True
    return False


def answer(types: list[str], query_id: int, *, echo_question: bool) -> bytes:
    packet = HEADER.pack(
        query_id, AUTHORITATIVE_RESPONSE, int(echo_question), len(types), 0, 0
    )
    if echo_question:
        packet += encode_name(ENUMERATION) + QUESTION.pack(PTR, IN)
    for service_type in types:
        target = encode_name(service_type)
        record = RECORD.pack(PTR, IN, SHARED_RECORD_TTL, len(target))
        packet += encode_name(ENUMERATION) + record + target
    return packet


def main() -> None:
    types = sys.argv[1:]
    if not types:
        raise SystemExit("usage: beacon.py SERVICE_TYPE...")
    listener = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    listener.bind(("", MDNS_PORT))
    membership = socket.inet_aton(MDNS_GROUP) + socket.inet_aton("0.0.0.0")
    listener.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, membership)
    listener.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 255)
    print(f"answering {ENUMERATION} with {' '.join(types)}", flush=True)
    while True:
        packet, sender = listener.recvfrom(9000)
        address, port = cast(tuple[str, int], sender)
        try:
            if not asks_for_enumeration(packet):
                continue
        except (IndexError, UnicodeDecodeError, ValueError, struct.error):
            continue
        # The proxy asks from an ephemeral port, which makes it a legacy querier owed
        # a unicast reply echoing its ID and question (RFC 6762 section 6.7). The
        # multicast copy is what the live experiment also sent, and it worked.
        if port != MDNS_PORT:
            query_id = HEADER.unpack_from(packet)[0]
            reply = answer(types, query_id, echo_question=True)
            listener.sendto(reply, (address, port))
        listener.sendto(answer(types, 0, echo_question=False), (MDNS_GROUP, MDNS_PORT))


if __name__ == "__main__":
    main()
