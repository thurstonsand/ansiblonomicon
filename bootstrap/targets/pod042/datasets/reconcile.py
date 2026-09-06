#!/usr/bin/python3
import argparse
from dataclasses import dataclass
import grp
import os
from pathlib import Path
import subprocess
import tomllib
from typing import cast

from pod042_storage import POOLS

LAYOUT = "org.ansiblonomicon:layout"
VERIFIED = "org.ansiblonomicon:migration"


@dataclass(frozen=True)
class Property:
    value: str
    source: str


@dataclass(frozen=True)
class Dataset:
    name: str
    mountpoint: str
    shared: bool


def record(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError("Expected a configuration table")
    result = cast(dict[object, object], value)
    if not all(isinstance(key, str) for key in result):
        raise ValueError("Expected string configuration keys")
    return cast(dict[str, object], result)


def strings(value: object) -> dict[str, str]:
    result = record(value)
    if not all(isinstance(item, str) for item in result.values()):
        raise ValueError("Expected string properties")
    return cast(dict[str, str], result)


def output(*args: str) -> str:
    return subprocess.check_output(args, text=True).strip()


def properties(name: str, keys: list[str]) -> dict[str, Property]:
    result: dict[str, Property] = {}
    for line in output(
        "/usr/sbin/zfs",
        "get",
        "-H",
        "-o",
        "property,value,source",
        ",".join(keys),
        name,
    ).splitlines():
        key, value, source = line.split("\t")
        result[key] = Property(value, source)
    return result


def converge(name: str, desired: dict[str, str], apply: bool) -> None:
    current = properties(name, list(desired))
    changes = [
        f"{key}={value}"
        for key, value in desired.items()
        if current[key].value != value or current[key].source != "local"
    ]
    if changes:
        print(f"{name}: {' '.join(changes)}", flush=True)
        if apply:
            subprocess.run(["/usr/sbin/zfs", "set", *changes, name], check=True)


def reconcile(config: Path, mode: str) -> None:
    if os.geteuid() != 0:
        raise ValueError("Root is required")
    for pool, guid in POOLS.items():
        if output("/usr/sbin/zpool", "get", "-H", "-o", "value", "guid", pool) != guid:
            raise ValueError(f"Unexpected pool GUID: {pool}")
    raw = tomllib.loads(config.read_text())
    desired = strings(raw["properties"])
    creation = strings(raw["creation"])
    datasets: list[Dataset] = []
    for name, value in record(raw["datasets"]).items():
        entry = record(value)
        mountpoint, shared = entry["mountpoint"], entry["shared"]
        if not isinstance(mountpoint, str) or not isinstance(shared, bool):
            raise ValueError(f"Invalid dataset declaration: {name}")
        if name.split("/")[0] not in POOLS or mountpoint != f"/mnt/{name}":
            raise ValueError(f"Unexpected dataset path: {name}")
        datasets.append(Dataset(name, mountpoint, shared))
    datasets.sort(key=lambda dataset: dataset.name)
    if grp.getgrnam("media").gr_gid != 3000:
        raise ValueError("Expected media group GID 3000")
    existing: dict[str, str] = {}
    for line in output(
        "/usr/sbin/zfs", "list", "-H", "-o", "name,type", "-r", *POOLS
    ).splitlines():
        name, kind = line.split("\t")
        existing[name] = kind
    for dataset in datasets:
        if dataset.name not in existing:
            if mode != "prepare":
                raise ValueError(
                    f"Prepare and verify the fresh dataset first: {dataset.name}"
                )
            path = Path(dataset.mountpoint)
            if path.is_symlink() or (
                path.exists() and (not path.is_dir() or any(path.iterdir()))
            ):
                raise ValueError(f"Refusing to cover an occupied mountpoint: {path}")
            continue
        if existing[dataset.name] != "filesystem":
            raise ValueError(f"Not a filesystem: {dataset.name}")
        current = properties(dataset.name, [LAYOUT, VERIFIED, *creation])
        if current[LAYOUT] != Property("fresh-v1", "local") or any(
            current[key].value != value for key, value in creation.items()
        ):
            raise ValueError(f"Refusing to adopt a legacy filesystem: {dataset.name}")
        if mode != "prepare" and current[VERIFIED] != Property("verified", "local"):
            raise ValueError(f"Migration verification is pending: {dataset.name}")
    quarantine: dict[str, dict[str, str]] = {}
    if mode != "prepare":
        for name, kind in existing.items():
            if any(name == dataset.name for dataset in datasets):
                continue
            pool = name.split("/")[0]
            if (
                name != pool
                and name != f"{pool}/legacy"
                and not name.startswith(f"{pool}/legacy/")
            ):
                raise ValueError(f"Unclassified legacy dataset: {name}")
            if kind == "filesystem":
                if properties(name, ["mounted"])["mounted"].value != "no":
                    raise ValueError(
                        f"Unmount the legacy filesystem before quarantine: {name}"
                    )
                quarantine[name] = {
                    "readonly": "on",
                    "canmount": "off",
                    "mountpoint": "none",
                }
            else:
                quarantine[name] = {"readonly": "on", "volmode": "none"}
    for dataset in datasets:
        values = {**desired, "mountpoint": dataset.mountpoint}
        if dataset.name not in existing:
            args = ["/usr/sbin/zfs", "create"]
            for key, value in {
                **creation,
                **values,
                LAYOUT: "fresh-v1",
                VERIFIED: "pending",
            }.items():
                args.extend(["-o", f"{key}={value}"])
            subprocess.run([*args, dataset.name], check=True)
            print(f"Created fresh dataset: {dataset.name}", flush=True)
        else:
            converge(dataset.name, values, mode != "check")
    for name, values in quarantine.items():
        converge(name, values, mode != "check")
    for dataset in datasets:
        if properties(dataset.name, ["mounted"])["mounted"].value == "no":
            print(f"Mount: {dataset.name}", flush=True)
            if mode != "check":
                subprocess.run(["/usr/sbin/zfs", "mount", dataset.name], check=True)
            else:
                continue
        if dataset.shared:
            metadata = Path(dataset.mountpoint).stat()
            if (metadata.st_uid, metadata.st_gid, metadata.st_mode & 0o7777) != (
                0,
                3000,
                0o2775,
            ):
                print(f"{dataset.mountpoint}: root:media mode 2775", flush=True)
                if mode != "check":
                    os.chown(dataset.mountpoint, 0, 3000)
                    os.chmod(dataset.mountpoint, 0o2775)
    print(
        f"Dataset policy {mode}: {len(datasets)} active, {len(quarantine)} quarantined",
        flush=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("prepare", "check", "apply"))
    parser.add_argument(
        "--config", type=Path, default=Path(__file__).with_name("layout.toml")
    )
    args = parser.parse_args()
    reconcile(args.config, args.mode)


if __name__ == "__main__":
    main()
