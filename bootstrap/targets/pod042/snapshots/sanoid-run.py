#!/usr/bin/python3
import subprocess
import sys

from pod042_storage import POOLS


def verify_datasets() -> None:
    guid = subprocess.run(
        ["/usr/sbin/zpool", "get", "-H", "-o", "value", "guid", "black-box"],
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    ).stdout.strip()
    if guid != POOLS["black-box"]:
        raise ValueError("Unexpected pool GUID for black-box")
    expected = {
        "org.ansiblonomicon:layout\tfresh-v1\tlocal",
        "org.ansiblonomicon:migration\tverified\tlocal",
    }
    for dataset in ("black-box/docker", "black-box/agents"):
        result = subprocess.run(
            [
                "/usr/sbin/zfs",
                "get",
                "-r",
                "-t",
                "filesystem,volume",
                "-H",
                "-o",
                "property,value,source",
                "org.ansiblonomicon:layout,org.ansiblonomicon:migration",
                dataset,
            ],
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )
        rows = result.stdout.splitlines()
        if set(rows) != expected or any(
            rows.count(row) * 2 != len(rows) for row in expected
        ):
            raise ValueError(f"Unverified snapshot dataset tree: {dataset}")


def main(args: list[str]) -> int:
    verify_datasets()
    result = subprocess.run(["/usr/sbin/sanoid", *args], stderr=subprocess.PIPE)
    sys.stderr.buffer.write(result.stderr)
    sys.stderr.buffer.flush()
    return result.returncode or int(bool(result.stderr))


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
