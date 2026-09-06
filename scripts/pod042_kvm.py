#!/usr/bin/env python3
"""Control pod042-kvm through its local HTTP and WebSocket APIs."""

import argparse
from collections.abc import Sequence
from datetime import datetime
import json
from pathlib import Path
import ssl
import subprocess
import sys
import tempfile
import time
from typing import Protocol, cast
from urllib.parse import urlsplit, urlunsplit

import httpx
from websockets.sync.client import ClientConnection, connect

DEFAULT_URL = "https://10.10.10.34"
OP_ITEM = "egtxppxa5funfi2o4biznocznm"
OP_VAULT = "agent"
SCREENSHOT_ATTEMPTS = 60

KEY_ALIASES = {
    "alt": "AltLeft",
    "backspace": "Backspace",
    "cmd": "MetaLeft",
    "control": "ControlLeft",
    "ctrl": "ControlLeft",
    "del": "Delete",
    "delete": "Delete",
    "down": "ArrowDown",
    "end": "End",
    "enter": "Enter",
    "esc": "Escape",
    "escape": "Escape",
    "home": "Home",
    "left": "ArrowLeft",
    "meta": "MetaLeft",
    "pagedown": "PageDown",
    "pageup": "PageUp",
    "printscreen": "PrintScreen",
    "return": "Enter",
    "right": "ArrowRight",
    "shift": "ShiftLeft",
    "space": "Space",
    "sysrq": "PrintScreen",
    "tab": "Tab",
    "up": "ArrowUp",
}


class KvmError(Exception):
    pass


class BinarySender(Protocol):
    def send(self, message: bytes) -> object: ...


def op_field(field: str) -> str:
    result = subprocess.run(
        [
            "op",
            "item",
            "get",
            OP_ITEM,
            "--vault",
            OP_VAULT,
            "--fields",
            field,
            "--reveal",
        ],
        check=True,
        stdout=subprocess.PIPE,
        text=True,
    )
    return result.stdout.rstrip("\n")


def response_result(response: httpx.Response, operation: str) -> dict[str, object]:
    response.raise_for_status()
    payload: object = response.json()
    if not isinstance(payload, dict):
        raise KvmError(f"{operation} returned a non-object response")
    body = cast(dict[str, object], payload)
    if body.get("ok") is not True:
        result = body.get("result")
        error = (
            cast(dict[str, object], result).get("error")
            if isinstance(result, dict)
            else None
        )
        raise KvmError(f"{operation} failed{f': {error}' if error else ''}")
    result = body.get("result")
    if not isinstance(result, dict):
        raise KvmError(f"{operation} returned no result")
    return cast(dict[str, object], result)


class KvmClient:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.http = httpx.Client(base_url=self.base_url, verify=False, timeout=30)
        self.token = ""

    def __enter__(self) -> KvmClient:
        username = op_field("username")
        password = op_field("password")
        result = response_result(
            self.http.post(
                "/api/auth/login",
                files={
                    "user": (None, username),
                    "passwd": (None, password),
                },
            ),
            "login",
        )
        token = result.get("token")
        if not isinstance(token, str) or not token:
            raise KvmError("login returned no token")
        self.token = token
        self.http.headers["token"] = token
        return self

    def __exit__(self, *_: object) -> None:
        self.http.close()

    def screenshot(self) -> bytes:
        with self.key_socket():
            last_status = 200
            for attempt in range(SCREENSHOT_ATTEMPTS):
                response = self.http.get("/api/streamer/snapshot")
                last_status = response.status_code
                if response.status_code not in {502, 503, 504}:
                    response.raise_for_status()
                    content = response.content
                    if content.startswith(b"\xff\xd8") and content.endswith(
                        b"\xff\xd9"
                    ):
                        return content
                if attempt < SCREENSHOT_ATTEMPTS - 1:
                    time.sleep(1)
        raise KvmError(
            f"screenshot remained unavailable after {SCREENSHOT_ATTEMPTS} attempts; "
            f"last HTTP status was {last_status}"
        )

    def type_text(self, text: str, keymap: str, slow: bool) -> None:
        response_result(
            self.http.post(
                "/api/hid/print",
                params={"limit": 0, "keymap": keymap, "slow": str(slow).lower()},
                content=text.encode(),
                headers={"content-type": "text/plain; charset=utf-8"},
            ),
            "text input",
        )

    def status(self) -> dict[str, object]:
        hostname = response_result(
            self.http.get("/api/system/get_hostname"), "hostname"
        )
        version = response_result(
            self.http.get("/api/upgrade/version"), "firmware version"
        )
        streamer = response_result(self.http.get("/api/streamer"), "streamer")
        return {
            "hostname": hostname.get("hostname"),
            "model": version.get("model"),
            "version": version.get("version"),
            "video_online": streamer.get("streamer") is not None,
        }

    def reboot(self) -> None:
        response_result(self.http.get("/api/upgrade/reboot"), "KVM reboot")

    def media_status(self) -> dict[str, object]:
        return response_result(self.http.get("/api/msd"), "virtual media status")

    def media_upload(self, path: Path) -> dict[str, object]:
        size = path.stat().st_size
        with path.open("rb") as image:
            return response_result(
                self.http.post(
                    "/api/msd/write",
                    params={"image": path.name, "remove_incomplete": "true"},
                    content=image,
                    headers={"content-length": str(size)},
                    timeout=None,
                ),
                "virtual media upload",
            )

    def media_mount(self, image: str, cdrom: bool, writable: bool) -> None:
        response_result(
            self.http.post(
                "/api/msd/set_params",
                params={
                    "image": image,
                    "cdrom": str(cdrom).lower(),
                    "rw": str(writable).lower(),
                },
            ),
            "virtual media selection",
        )
        response_result(
            self.http.post("/api/msd/set_connected", params={"connected": "true"}),
            "virtual media mount",
        )

    def media_eject(self) -> None:
        response_result(
            self.http.post("/api/msd/set_connected", params={"connected": "false"}),
            "virtual media eject",
        )

    def media_enable(self, enabled: bool) -> None:
        value = str(enabled).lower()
        response_result(
            self.http.post(
                "/api/system/otg_functions",
                params={"start_cdrom": value, "start_flash": value},
            ),
            f"virtual media {'enable' if enabled else 'disable'}",
        )

    def media_remove(self, image: str) -> None:
        response_result(
            self.http.post("/api/msd/remove", params={"image": image}),
            "virtual media removal",
        )

    def key_socket(self) -> ClientConnection:
        parts = urlsplit(self.base_url)
        scheme = "wss" if parts.scheme == "https" else "ws"
        url = urlunsplit((scheme, parts.netloc, "/api/ws", "", ""))
        context = None
        if scheme == "wss":
            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
        try:
            return connect(
                url,
                ssl=context,
                additional_headers={"token": self.token},
                open_timeout=10,
            )
        except Exception:
            raise KvmError("KVM WebSocket connection failed") from None


def key_code(name: str) -> str:
    lowered = name.lower()
    if lowered in KEY_ALIASES:
        return KEY_ALIASES[lowered]
    if len(name) == 1 and name.isascii() and name.isalpha():
        return f"Key{name.upper()}"
    if len(name) == 1 and name.isascii() and name.isdigit():
        return f"Digit{name}"
    if lowered.startswith("f") and lowered[1:].isdigit():
        number = int(lowered[1:])
        if 1 <= number <= 20:
            return f"F{number}"
    if name and name[0].isupper() and name.isascii() and name.isalnum():
        return name
    raise KvmError(f"unknown key name: {name}")


def parse_chord(chord: str) -> list[str]:
    keys = [key_code(part) for part in chord.split("+") if part]
    if not keys:
        raise KvmError("a key chord cannot be empty")
    if len(keys) != len(set(keys)):
        raise KvmError(f"a key chord cannot repeat a key: {chord}")
    return keys


def key_frame(code: str, down: bool) -> bytes:
    return bytes((0x01, int(down))) + code.encode("ascii")


def send_chord(connection: BinarySender, keys: Sequence[str], delay: float) -> None:
    pressed: list[str] = []
    try:
        for key in keys:
            connection.send(key_frame(key, True))
            pressed.append(key)
            time.sleep(delay)
    finally:
        for key in reversed(pressed):
            connection.send(key_frame(key, False))
            time.sleep(delay)


def default_screenshot_path() -> Path:
    timestamp = datetime.now().astimezone().strftime("%Y%m%d-%H%M%S")
    return Path(tempfile.gettempdir()) / f"pod042-kvm-{timestamp}.jpg"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=DEFAULT_URL)
    commands = parser.add_subparsers(dest="command", required=True)

    screenshot = commands.add_parser("screenshot", help="Save the current frame")
    screenshot.add_argument("path", nargs="?", type=Path)

    text = commands.add_parser("text", help="Type literal text")
    text.add_argument("text", nargs="*")
    text.add_argument("--enter", action="store_true", help="Append a newline")
    text.add_argument("--keymap", default="en-us")
    text.add_argument("--slow", action="store_true")

    key = commands.add_parser("key", help="Press keys or modifier chords")
    key.add_argument("chords", nargs="+", help="Examples: enter ctrl+alt+delete")
    key.add_argument("--delay", type=float, default=0.1)

    media = commands.add_parser("media", help="Manage virtual media")
    media_commands = media.add_subparsers(dest="media_command", required=True)
    media_commands.add_parser("status", help="Show storage and mount state")
    upload = media_commands.add_parser("upload", help="Upload an image")
    upload.add_argument("path", type=Path)
    mount = media_commands.add_parser("mount", help="Expose an uploaded image")
    mount.add_argument("image")
    mount.add_argument("--disk", action="store_true", help="Emulate a disk, not CD-ROM")
    mount.add_argument("--writable", action="store_true")
    media_commands.add_parser("eject", help="Disconnect virtual media")
    media_commands.add_parser("enable", help="Enable the USB storage functions")
    media_commands.add_parser("disable", help="Disable the USB storage functions")
    remove = media_commands.add_parser("remove", help="Delete an uploaded image")
    remove.add_argument("image")

    commands.add_parser(
        "reboot", help="Reboot the KVM appliance, not the controlled host"
    )
    commands.add_parser("status", help="Show appliance and video status")
    return parser


def run(argv: Sequence[str]) -> int:
    args = build_parser().parse_args(argv)
    with KvmClient(args.url) as client:
        if args.command == "screenshot":
            path = args.path or default_screenshot_path()
            path.write_bytes(client.screenshot())
            print(path)
        elif args.command == "text":
            if args.text:
                text = " ".join(args.text)
            elif sys.stdin.isatty():
                raise KvmError("text requires arguments or standard input")
            else:
                text = sys.stdin.read()
            client.type_text(
                text + ("\n" if args.enter else ""), args.keymap, args.slow
            )
        elif args.command == "key":
            with client.key_socket() as connection:
                for chord in args.chords:
                    send_chord(connection, parse_chord(chord), args.delay)
        elif args.command == "media":
            if args.media_command == "status":
                print(json.dumps(client.media_status(), indent=2))
            elif args.media_command == "upload":
                print(json.dumps(client.media_upload(args.path), indent=2))
            elif args.media_command == "mount":
                if args.writable and not args.disk:
                    raise KvmError("writable virtual media requires --disk")
                client.media_mount(args.image, not args.disk, args.writable)
            elif args.media_command == "eject":
                client.media_eject()
            elif args.media_command == "enable":
                client.media_enable(True)
            elif args.media_command == "disable":
                client.media_enable(False)
            elif args.media_command == "remove":
                client.media_remove(args.image)
        elif args.command == "reboot":
            client.reboot()
        elif args.command == "status":
            print(json.dumps(client.status(), indent=2))
    return 0


def main() -> int:
    try:
        return run(sys.argv[1:])
    except (KvmError, httpx.HTTPError, subprocess.CalledProcessError) as error:
        print(f"pod042-kvm: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
