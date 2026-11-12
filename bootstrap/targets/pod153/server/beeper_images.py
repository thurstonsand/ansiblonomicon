"""Hands agents a message's image, shrunk for vision models.

POST /beeper/images {"chat", "message", "index"} reads that attachment through Beeper Desktop's API
with the caller's own Beeper token, shrinks it, and answers with the JPEG as an MCP image block,
which Executor delivers to the agent as an image. The tunnel keeps it behind Cloudflare Access.
"""

import argparse
import base64
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import subprocess
import tempfile
from typing import Required, TypedDict
import urllib.error
import urllib.parse
import urllib.request

BEEPER = "http://127.0.0.1:23373"
# Anthropic's guidance: images beyond 1568 px on the long edge are scaled down before the model sees them.
LONG_EDGE = 1568


class Attachment(TypedDict, total=False):
    type: Required[str]
    id: str
    posterImg: str


class Message(TypedDict, total=False):
    attachments: list[Attachment]


class Failure(Exception):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status


def beeper(path: str, authorization: str) -> bytes:
    request = urllib.request.Request(
        BEEPER + path, headers={"Authorization": authorization}
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return response.read()
    except urllib.error.HTTPError as error:
        raise Failure(
            error.code, f"Beeper answered {error.code} for {path.split('?')[0]}"
        ) from error
    except urllib.error.URLError as error:
        raise Failure(
            HTTPStatus.SERVICE_UNAVAILABLE, f"Beeper Desktop is not answering: {error}"
        ) from error


def size(image: Path) -> tuple[int, int]:
    report = subprocess.run(
        ["/usr/bin/sips", "-g", "pixelWidth", "-g", "pixelHeight", str(image)],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    values = dict(
        line.strip().split(": ") for line in report.split("\n")[1:] if ": " in line
    )
    # sips reports an unreadable image as <nil> and still exits 0.
    if not values.get("pixelWidth", "").isdigit():
        raise Failure(
            HTTPStatus.UNPROCESSABLE_ENTITY,
            "the attachment is not an image sips can read",
        )
    return int(values["pixelWidth"]), int(values["pixelHeight"])


def shrink(original: bytes, out: Path) -> tuple[int, int]:
    with tempfile.TemporaryDirectory() as scratch:
        source, flat = Path(scratch, "original"), Path(scratch, "flat.bmp")
        source.write_bytes(original)
        try:
            # -Z scales up as readily as down, so only a large image gets it.
            fit = ["-Z", str(LONG_EDGE)] if max(size(source)) > LONG_EDGE else []
            # By way of a bitmap, which holds no EXIF, so the copy an agent sees keeps no location
            # or camera details, and its orientation is applied to the pixels.
            for args in (
                ["-s", "format", "bmp", *fit, str(source), "--out", str(flat)],
                ["-s", "format", "jpeg", str(flat), "--out", str(out)],
            ):
                subprocess.run(
                    ["/usr/bin/sips", *args], check=True, capture_output=True
                )
        except subprocess.CalledProcessError as error:
            raise Failure(
                HTTPStatus.UNPROCESSABLE_ENTITY,
                f"sips could not read the attachment: {error.stderr.decode().strip()}",
            ) from error
    return size(out)


class Handler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        if self.path != "/beeper/images":
            return self.send_error(HTTPStatus.NOT_FOUND)
        try:
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            chat, message, index = (
                str(body["chat"]),
                str(body["message"]),
                int(body["index"]),
            )
            authorization = self.headers["Authorization"]
            if not authorization:
                raise Failure(HTTPStatus.UNAUTHORIZED, "missing Beeper token")
            found: Message = json.loads(
                beeper(
                    f"/v1/chats/{urllib.parse.quote(chat, safe='')}/messages/{urllib.parse.quote(message, safe='')}",
                    authorization,
                )
            )
            attachments = found.get("attachments") or []
            if not 0 <= index < len(attachments):
                raise Failure(
                    HTTPStatus.NOT_FOUND,
                    f"message has {len(attachments)} attachments, no index {index}",
                )
            attachment = attachments[index]
            source = (
                attachment.get("posterImg")
                if attachment["type"] == "video"
                else attachment.get("id")
            )
            if attachment["type"] not in ("img", "video") or not source:
                raise Failure(
                    HTTPStatus.UNPROCESSABLE_ENTITY,
                    f"attachment {index} is {attachment['type']} with no image",
                )
            # Beeper also serves file:// URLs, which would hand an agent whatever local file a sender named.
            if not source.startswith(("mxc://", "localmxc://")):
                raise Failure(
                    HTTPStatus.UNPROCESSABLE_ENTITY,
                    f"attachment {index} is not a Matrix asset",
                )
            original = beeper(
                f"/v1/assets/serve?{urllib.parse.urlencode({'url': source})}",
                authorization,
            )
            with tempfile.TemporaryDirectory() as scratch:
                out = Path(scratch, "image.jpg")
                width, height = shrink(original, out)
                data = out.read_bytes()
        except Failure as failure:
            return self.answer(failure.status, {"error": str(failure)})
        self.answer(
            HTTPStatus.OK,
            {
                "image": {
                    "type": "image",
                    "mimeType": "image/jpeg",
                    "data": base64.b64encode(data).decode(),
                },
                "width": width,
                "height": height,
            },
        )

    def answer(self, status: int, payload: dict[str, object]) -> None:
        data = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, required=True)
    args = parser.parse_args()
    ThreadingHTTPServer(("127.0.0.1", args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
