import argparse
import errno
import fcntl
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time

CADDY = Path(__file__).resolve().parent / "caddy"
SITE = CADDY / "site" / "f"
EXPIRY = "user.ansiblonomicon.public-file-expiry"
TIMER = "ansiblonomicon-public-file-expiry.timer"


def duration_seconds(value: str) -> int:
    match = re.fullmatch(r"([1-9][0-9]*)([smhd])", value)
    if match is None:
        raise argparse.ArgumentTypeError(
            "use a positive duration such as 30m, 2h, or 7d"
        )
    count, unit = match.groups()
    return int(count) * {"s": 1, "m": 60, "h": 3600, "d": 86400}[unit]


def share_name(value: str) -> str:
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9._-]{0,254}", value) or value in {
        "index.html",
        "index.txt",
    }:
        raise argparse.ArgumentTypeError(f"invalid share name: {value}")
    return value


def deadline(path: Path) -> int | None:
    try:
        return int(os.getxattr(path, EXPIRY, follow_symlinks=False))
    except OSError as error:
        if error.errno != errno.ENODATA:
            raise
        return None


def arm_file(path: Path, seconds: int) -> None:
    expires = time.time_ns() + seconds * 1_000_000_000
    os.setxattr(path, EXPIRY, str(expires).encode(), follow_symlinks=False)


def publish(path: Path, size: int, seconds: int | None) -> None:
    with tempfile.NamedTemporaryFile(dir=CADDY) as staged:
        shutil.copyfileobj(sys.stdin.buffer, staged)
        staged.flush()
        received = staged.tell()
        if received != size:
            raise SystemExit(f"expected {size} bytes, received {received}: {path.name}")
        os.fchmod(staged.fileno(), 0o644)
        if seconds is not None:
            arm_file(Path(staged.name), seconds)
        try:
            os.link(staged.name, path)
        except FileExistsError:
            raise SystemExit(f"share already exists: {path.name}") from None


def main() -> None:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("expire")
    add = commands.add_parser("add")
    add.add_argument("name", type=share_name)
    add.add_argument("--size", type=int, required=True)
    lifetime = add.add_mutually_exclusive_group()
    lifetime.add_argument(
        "--ttl", dest="duration", type=duration_seconds, default="24h"
    )
    lifetime.add_argument(
        "--forever", dest="duration", action="store_const", const=None
    )
    arm = commands.add_parser("arm")
    arm.add_argument("name", type=share_name)
    arm.add_argument("duration", type=duration_seconds)
    commands.add_parser("disarm").add_argument("name", type=share_name)
    commands.add_parser("remove").add_argument("name", type=share_name)
    args = parser.parse_args()

    if args.command in {"add", "arm"} and args.duration is not None:
        active = subprocess.run(
            ["/usr/bin/systemctl", "is-active", "--quiet", TIMER], check=False
        )
        if active.returncode != 0:
            parser.error(f"expiry timer is not active: {TIMER}")

    if args.command == "add":
        publish(SITE / args.name, args.size, args.duration)
        return

    with (CADDY / ".public-file.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if args.command == "expire":
            now = time.time_ns()
            for path in SITE.iterdir():
                if path.is_file(follow_symlinks=False):
                    expires = deadline(path)
                    if expires is not None and expires <= now:
                        path.unlink()
                        print(f"Expired {path.name}")
            return

        path = SITE / args.name
        if args.command == "remove":
            path.unlink(missing_ok=True)
            return
        if not path.is_file(follow_symlinks=False):
            parser.error(f"share does not exist: {args.name}")
        if args.command == "arm":
            assert args.duration is not None
            arm_file(path, args.duration)
        elif deadline(path) is not None:
            os.removexattr(path, EXPIRY, follow_symlinks=False)


if __name__ == "__main__":
    main()
