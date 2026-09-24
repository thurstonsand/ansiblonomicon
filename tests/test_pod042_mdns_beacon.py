from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import struct
import sys
from typing import Any

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
STACK = ROOT / "bootstrap/targets/pod042/containers/stacks/mdns-beacon"
SPEC = spec_from_file_location("pod042_mdns_beacon", STACK / "beacon.py")
assert SPEC is not None
assert SPEC.loader is not None
beacon: Any = module_from_spec(SPEC)
sys.modules[SPEC.name] = beacon
SPEC.loader.exec_module(beacon)

PRINTER_TYPES = ["_ipp._tcp.local", "_uscan._tcp.local"]


def query(*questions: tuple[bytes, int], flags: int = 0) -> bytes:
    packet = struct.pack("!6H", 7, flags, len(questions), 0, 0, 0)
    for name, record_type in questions:
        packet += name + struct.pack("!HH", record_type, 1)
    return packet


def pointer_types(packet: bytes) -> list[str]:
    _, _, questions, answers, _, _ = beacon.HEADER.unpack_from(packet)
    offset = beacon.HEADER.size
    for _ in range(questions):
        _, offset = beacon.read_name(packet, offset)
        offset += beacon.QUESTION.size
    targets: list[str] = []
    for _ in range(answers):
        owner, offset = beacon.read_name(packet, offset)
        record_type, _, _, length = beacon.RECORD.unpack_from(packet, offset)
        offset += beacon.RECORD.size
        assert (owner, record_type) == (beacon.ENUMERATION, beacon.PTR)
        targets.append(beacon.read_name(packet, offset)[0])
        offset += length
    return targets


def test_mdns_beacon_holds_the_named_scanners_identity() -> None:
    compose = yaml.safe_load((STACK / "compose.yaml").read_text())
    clients = (ROOT / "terraform/unifi/clients.tf").read_text()
    service = compose["services"]["mdns-beacon"]
    identity = service["networks"]["scanners"]
    network = compose["networks"]["scanners"]
    assert network["driver"] == "macvlan"
    assert network["driver_opts"] == {"parent": "enp5s0.40"}
    assert f'fixed_ip       = "{identity["ipv4_address"]}"' in clients
    assert f'mac            = "{identity["mac_address"]}"' in clients
    assert "ports" not in service
    assert service["cap_drop"] == ["ALL"]
    assert service["read_only"] is True


def test_mdns_beacon_recognises_enumeration_by_name_and_type() -> None:
    enumeration = beacon.encode_name(beacon.ENUMERATION)
    assert beacon.asks_for_enumeration(query((enumeration, beacon.PTR)))
    assert beacon.asks_for_enumeration(query((enumeration.upper(), beacon.ANY)))
    assert not beacon.asks_for_enumeration(
        query((beacon.encode_name("_ipp._tcp.local"), beacon.PTR))
    )
    assert not beacon.asks_for_enumeration(query((enumeration, 1)))
    assert not beacon.asks_for_enumeration(
        query((enumeration, beacon.PTR), flags=beacon.RESPONSE_BIT)
    )


def test_mdns_beacon_follows_compressed_question_names() -> None:
    first = beacon.encode_name("_ipp._tcp.local")
    local_offset = beacon.HEADER.size + first.index(b"\x05local")
    compressed = b"\x09_services\x07_dns-sd\x04_udp" + struct.pack(
        "!H", 0xC000 | local_offset
    )
    packet = query((first, beacon.PTR), (compressed, beacon.PTR))
    assert beacon.asks_for_enumeration(packet)


def test_mdns_beacon_rejects_forward_compression_pointers() -> None:
    looping = struct.pack("!H", 0xC000 | beacon.HEADER.size)
    with pytest.raises(ValueError, match="backwards"):
        beacon.asks_for_enumeration(query((looping, beacon.PTR)))


def test_mdns_beacon_answers_legacy_queriers_with_their_question() -> None:
    reply = beacon.answer(PRINTER_TYPES, 483, echo_question=True)
    query_id, flags, questions, answers, _, _ = beacon.HEADER.unpack_from(reply)
    assert (query_id, flags, questions, answers) == (483, 0x8400, 1, 2)
    assert beacon.read_name(reply, beacon.HEADER.size)[0] == beacon.ENUMERATION
    assert pointer_types(reply) == PRINTER_TYPES


def test_mdns_beacon_multicast_answer_names_only_types() -> None:
    reply = beacon.answer(PRINTER_TYPES, 0, echo_question=False)
    assert beacon.HEADER.unpack_from(reply)[:4] == (0, 0x8400, 0, 2)
    assert pointer_types(reply) == PRINTER_TYPES
