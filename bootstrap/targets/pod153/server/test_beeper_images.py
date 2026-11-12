"""Run on macOS, which supplies sips: python3 -m unittest discover -s bootstrap/targets/pod153/server"""

import base64
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import struct
import tempfile
import threading
from typing import cast, override
import unittest
import urllib.request
import zlib

import beeper_images

CHAT = "!chat:beeper.local"
MESSAGE = "42"
ASSET = "mxc://local.beeper.com/photo"
TOKEN = "Bearer test"


def png(width: int, height: int) -> bytes:
    def chunk(kind: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + kind
            + data
            + struct.pack(">I", zlib.crc32(kind + data))
        )

    rows = b"".join(b"\x00" + b"\xc8\x30\x30" * width for _ in range(height))
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(rows))
        + chunk(b"IEND", b"")
    )


# Wider than tall and over the 1568 px long edge, so a swapped or unscaled size shows.
PHOTO = png(2000, 1000)


class FakeBeeper(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.headers["Authorization"] != TOKEN:
            return self.send_error(401)
        if self.path == "/v1/chats/%21chat%3Abeeper.local/messages/42":
            body = json.dumps({"attachments": [{"type": "img", "id": ASSET}]}).encode()
        elif self.path == "/v1/assets/serve?url=mxc%3A%2F%2Flocal.beeper.com%2Fphoto":
            body = PHOTO
        else:
            return self.send_error(404)
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    @override
    def log_message(self, format: str, *args: object) -> None:
        pass


class QuietHandler(beeper_images.Handler):
    @override
    def log_message(self, format: str, *args: object) -> None:
        pass


def serve(handler: type[BaseHTTPRequestHandler]) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def jpeg_size(data: bytes) -> tuple[int, int]:
    with tempfile.NamedTemporaryFile(suffix=".jpg") as file:
        _ = file.write(data)
        file.flush()
        return beeper_images.size(Path(file.name))


class BeeperImagesTest(unittest.TestCase):
    @override
    def setUp(self) -> None:
        beeper = serve(FakeBeeper)
        self.addCleanup(beeper.server_close)
        self.addCleanup(beeper.shutdown)
        beeper_images.BEEPER = f"http://127.0.0.1:{beeper.server_port}"
        self.cache = Path(tempfile.mkdtemp())
        QuietHandler.cache = self.cache
        QuietHandler.public = "https://example.test/img/"
        server = serve(QuietHandler)
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        self.base = f"http://127.0.0.1:{server.server_port}"

    def post(self, **extra: object) -> dict[str, object]:
        request = urllib.request.Request(
            f"{self.base}/beeper/images",
            data=json.dumps(
                {"chat": CHAT, "message": MESSAGE, "index": 0, **extra}
            ).encode(),
            headers={"Authorization": TOKEN, "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request) as response:
            return json.load(response)

    def test_inline_answers_an_mcp_image_block_and_keeps_no_copy(self) -> None:
        answer = self.post(inline=True)
        image = cast(dict[str, object], answer["image"])
        self.assertEqual((image["type"], image["mimeType"]), ("image", "image/jpeg"))
        data = base64.b64decode(str(image["data"]), validate=True)
        self.assertEqual(data[:3], b"\xff\xd8\xff")
        self.assertEqual(jpeg_size(data), (1568, 784))
        self.assertEqual((answer["width"], answer["height"]), (1568, 784))
        self.assertNotIn("url", answer)
        self.assertEqual(list(self.cache.iterdir()), [])

    def test_without_inline_answers_a_url_that_serves_the_image(self) -> None:
        answer = self.post()
        url = str(answer["url"])
        self.assertTrue(url.startswith("https://example.test/img/"))
        name = url.removeprefix("https://example.test/img/")
        with urllib.request.urlopen(f"{self.base}/img/{name}") as response:
            self.assertEqual(response.headers["Content-Type"], "image/jpeg")
            self.assertEqual(jpeg_size(response.read()), (1568, 784))


if __name__ == "__main__":
    unittest.main()
