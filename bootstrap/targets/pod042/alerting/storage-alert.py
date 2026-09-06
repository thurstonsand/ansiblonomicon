#!/usr/bin/python3
import http.client
import json
import os
import stat
import sys
from typing import IO, cast
import urllib.error
import urllib.parse
import urllib.request
import uuid


class NoRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: IO[bytes],
        code: int,
        msg: str,
        headers: http.client.HTTPMessage,
        newurl: str,
    ) -> None:
        return None


def fail(message: str) -> int:
    print(f"storage-alert: {message}", file=sys.stderr)
    return 1


def main() -> int:
    if len(sys.argv) < 2:
        print(
            "usage: storage-alert <title> [body...] (or body on stdin)", file=sys.stderr
        )
        return 64
    if os.geteuid() != 0:
        return fail("run as root to read /etc/alerting/hark-webhook-url")

    body = " ".join(sys.argv[2:])
    if not body and not sys.stdin.isatty():
        body = sys.stdin.read()
    payload = {
        "title": f"pod042: {sys.argv[1]}"[:80],
        "body": (body.strip() or "(no detail)")[:2000],
    }

    try:
        descriptor = os.open(
            "/etc/alerting/hark-webhook-url",
            os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
        )
        with os.fdopen(descriptor, encoding="utf-8") as credential:
            metadata = os.fstat(credential.fileno())
            if (
                not stat.S_ISREG(metadata.st_mode)
                or metadata.st_uid != 0
                or metadata.st_gid != 0
                or stat.S_IMODE(metadata.st_mode) != 0o600
                or metadata.st_nlink != 1
            ):
                return fail(
                    "credential must be a root-owned regular file with mode 0600; reconcile alerting"
                )
            webhook = credential.read().strip()
        url = urllib.parse.urlsplit(webhook)
        if (
            url.scheme != "https"
            or not url.hostname
            or url.username is not None
            or url.password is not None
            or url.fragment
            or any(character.isspace() for character in webhook)
        ):
            return fail(
                "credential must contain an HTTPS webhook URL; reconcile alerting"
            )
    except (OSError, ValueError):
        return fail(
            "cannot read a valid credential at /etc/alerting/hark-webhook-url; reconcile alerting"
        )

    try:
        request = urllib.request.Request(
            webhook,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Idempotency-Key": str(uuid.uuid4()),
            },
            method="POST",
        )
        opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({}), NoRedirects()
        )
        with opener.open(request, timeout=15) as response:
            raw: object = json.load(response)
        if not isinstance(raw, dict):
            return fail("Hark returned an invalid response")
        result = cast(dict[str, object], raw)
        if result.get("ok") is not True:
            return fail("Hark did not accept the notification; check the Hark service")
        delivered = result.get("delivered")
        if type(delivered) is not int or delivered < 1:
            return fail(
                "Hark accepted no device deliveries; check the Hark device registration"
            )
    except urllib.error.HTTPError as error:
        return fail(
            f"Hark returned HTTP {error.code}; check the service credential and Hark status"
        )
    except (OSError, ValueError, http.client.HTTPException):
        return fail("delivery failed; check network, TLS trust, and Hark availability")
    return 0


if __name__ == "__main__":
    sys.exit(main())
