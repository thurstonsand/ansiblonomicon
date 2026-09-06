#!/usr/bin/python3
import argparse
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import stat
import subprocess

from pod042_storage import POOLS

ACL_XATTRS = {
    "system.posix_acl_access",
    "system.posix_acl_default",
    "system.nfs4_acl",
    "security.NTACL",
    "user.NTACL",
}


@dataclass(frozen=True)
class Copy:
    source: Path
    source_dataset: str
    target: Path
    dataset: str
    shared: bool
    omit: tuple[str, ...]
    extra: tuple[str, ...]


COPIES = {
    "media": Copy(
        Path("/mnt/ark/watch"),
        "ark/watch",
        Path("/mnt/ark/media"),
        "ark/media",
        True,
        (),
        (),
    ),
    "anypod": Copy(
        Path("/mnt/ark/watch/anypod"),
        "ark/watch",
        Path("/mnt/ark/anypod"),
        "ark/anypod",
        True,
        ("data/db",),
        (),
    ),
    "docker": Copy(
        Path("/mnt/.pod042-migration/docker"),
        "black-box/legacy/docker",
        Path("/mnt/black-box/docker"),
        "black-box/docker",
        False,
        (),
        ("plex", "anypod/db"),
    ),
    "plex": Copy(
        Path("/mnt/black-box/apps/plex"),
        "black-box/apps/plex",
        Path("/mnt/black-box/docker/plex"),
        "black-box/docker/plex",
        False,
        (),
        (),
    ),
    "anypod-db": Copy(
        Path("/mnt/ark/watch/anypod/data/db"),
        "ark/watch",
        Path("/mnt/black-box/docker/anypod/db"),
        "black-box/docker/anypod",
        False,
        (),
        (),
    ),
}


def excluded(relative: str, prefixes: tuple[str, ...]) -> bool:
    return any(
        relative == prefix or relative.startswith(prefix + "/") for prefix in prefixes
    )


def entries(root: Path, omit: tuple[str, ...]):
    device = root.stat().st_dev
    pending = [root]
    while pending:
        path = pending.pop()
        relative = str(path.relative_to(root))
        if excluded(relative, omit):
            continue
        metadata = path.lstat()
        if metadata.st_dev != device:
            raise ValueError(f"Unexpected source mount: {path}")
        yield relative, path, metadata
        if stat.S_ISDIR(metadata.st_mode):
            pending.extend(sorted(path.iterdir(), reverse=True))


def attributes(path: Path) -> dict[str, bytes]:
    return {
        name: os.getxattr(path, name, follow_symlinks=False)
        for name in os.listxattr(path, follow_symlinks=False)
        if name not in ACL_XATTRS
    }


def mappings(name: str, copy: Copy) -> list[tuple[Path, Path]]:
    if name == "media":
        names = sorted(path.name for path in (copy.source / "media").iterdir())
        if names != ["movies", "podcasts", "tv"]:
            raise ValueError("Unclassified media directory")
        return [
            (copy.source / "media" / child, copy.target / child) for child in names
        ] + [(copy.source / "downloads", copy.target / "downloads")]
    return [(copy.source, copy.target)]


def preflight(name: str, copy: Copy) -> int:
    if name == "media" and {path.name for path in copy.source.iterdir()} != {
        "media",
        "downloads",
        "anypod",
        "ghost",
        "ghost_mysql",
        ".Trash-3001",
        "recycle",
        "copy",
        "transcode",
        "smb",
    }:
        raise ValueError("Unclassified watch directory")
    unique: set[tuple[int, int]] = set()
    size = 0
    for source, _target in mappings(name, copy):
        for _relative, path, metadata in entries(source, copy.omit):
            for attribute in os.listxattr(path, follow_symlinks=False):
                if attribute.startswith("system.") and attribute not in {
                    "system.posix_acl_access",
                    "system.posix_acl_default",
                }:
                    raise ValueError(
                        f"Classify unsupported source xattr {attribute}: {path}"
                    )
            key = metadata.st_dev, metadata.st_ino
            if stat.S_ISREG(metadata.st_mode) and key not in unique:
                unique.add(key)
                size += metadata.st_size
    pool = copy.dataset.split("/")[0]
    available = int(
        subprocess.check_output(
            ["zfs", "get", "-Hp", "-o", "value", "available", pool], text=True
        )
    )
    floor = 1024**4 if pool == "ark" else 16 * 1024**3
    if available < size + floor:
        raise ValueError("Insufficient headroom for an ordinary-copy fallback")
    acltype = subprocess.check_output(
        ["zfs", "get", "-H", "-o", "value", "acltype", copy.source_dataset], text=True
    ).strip()
    print(
        f"{name}: {len(unique)} unique files, {size} logical bytes; {available} available, {floor} reserved safety margin; source ACL type {acltype}",
        flush=True,
    )
    return size


def walk_error(error: OSError) -> None:
    raise error


def normalize(name: str, copy: Copy) -> None:
    for source, target in mappings(name, copy):
        for relative, _path, metadata in entries(source, copy.omit):
            destination = target / relative
            for attribute in os.listxattr(destination, follow_symlinks=False):
                if attribute in ACL_XATTRS:
                    os.removexattr(destination, attribute, follow_symlinks=False)
            if copy.shared:
                os.chown(
                    destination,
                    0 if destination == copy.target else -1,
                    3000,
                    follow_symlinks=False,
                )
                if stat.S_ISDIR(metadata.st_mode):
                    os.chmod(destination, 0o2775)
                elif stat.S_ISREG(metadata.st_mode):
                    os.chmod(destination, 0o664 | (metadata.st_mode & 0o111))


def compare_bytes(source: Path, target: Path, size: int, full: bool) -> None:
    with source.open("rb") as original, target.open("rb") as copied:
        if full:
            if (
                hashlib.file_digest(original, "sha256").digest()
                != hashlib.file_digest(copied, "sha256").digest()
            ):
                raise ValueError(f"Content mismatch: {target}")
        else:
            for position in (0, max(0, size // 2 - 32768), max(0, size - 65536)):
                original.seek(position)
                copied.seek(position)
                if original.read(65536) != copied.read(65536):
                    raise ValueError(f"Sample mismatch: {target}")


def verify(name: str, copy: Copy) -> None:
    expected: set[str] = set()
    hardlinks: dict[tuple[int, int], tuple[int, int]] = {}
    count = size = hashed = sampled = 0
    for source, target in mappings(name, copy):
        for relative, path, before in entries(source, copy.omit):
            destination = target / relative
            expected.add(str(destination.relative_to(copy.target)))
            after = destination.lstat()
            mode = stat.S_IMODE(before.st_mode)
            uid, gid = before.st_uid, before.st_gid
            if copy.shared:
                gid = 3000
                if destination == copy.target:
                    uid = 0
                if stat.S_ISDIR(before.st_mode):
                    mode = 0o2775
                elif stat.S_ISREG(before.st_mode):
                    mode = 0o664 | (before.st_mode & 0o111)
            if (stat.S_IFMT(before.st_mode), uid, gid, mode) != (
                stat.S_IFMT(after.st_mode),
                after.st_uid,
                after.st_gid,
                stat.S_IMODE(after.st_mode),
            ):
                raise ValueError(f"Metadata mismatch: {destination}")
            if attributes(path) != attributes(destination) or any(
                attr in ACL_XATTRS
                for attr in os.listxattr(destination, follow_symlinks=False)
            ):
                raise ValueError(f"Extended attribute mismatch: {destination}")
            if stat.S_ISLNK(before.st_mode):
                if os.readlink(path) != os.readlink(destination):
                    raise ValueError(f"Symlink mismatch: {destination}")
            elif stat.S_ISREG(before.st_mode):
                if (before.st_size, before.st_mtime_ns) != (
                    after.st_size,
                    after.st_mtime_ns,
                ):
                    raise ValueError(f"Size/mtime mismatch: {destination}")
                key = before.st_dev, before.st_ino
                identity = after.st_dev, after.st_ino
                if (
                    before.st_nlink > 1
                    and hardlinks.setdefault(key, identity) != identity
                ):
                    raise ValueError(f"Hardlink mismatch: {destination}")
                full = (
                    before.st_size <= (1024**2 if copy.shared else 16 * 1024**2)
                    or path.suffix in (".db", ".sqlite", ".sqlite3")
                    or path.name.endswith(("-wal", "-shm"))
                )
                sample = hashlib.sha256(os.fsencode(path)).digest()[0] == 0
                if full or sample:
                    compare_bytes(path, destination, before.st_size, full)
                    hashed += full
                    sampled += not full
                count += 1
                size += before.st_size
    for base, directories, files in os.walk(
        copy.target, followlinks=False, onerror=walk_error
    ):
        for child in directories + files:
            relative = str((Path(base) / child).relative_to(copy.target))
            if not excluded(relative, copy.extra) and relative not in expected:
                raise ValueError(f"Unexpected destination entry: {relative}")
        directories[:] = [
            child
            for child in directories
            if not excluded(
                str((Path(base) / child).relative_to(copy.target)), copy.extra
            )
        ]
    print(
        f"{name}: verified {count} files, {size} logical bytes, {hashed} full SHA256 comparisons, {sampled} large-file samples",
        flush=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("operation", choices=("copy", "verify"))
    parser.add_argument("group", choices=COPIES)
    args = parser.parse_args()
    copy = COPIES[args.group]
    if os.geteuid() != 0:
        raise ValueError("Root is required")
    for pool, guid in POOLS.items():
        if (
            subprocess.check_output(
                ["zpool", "get", "-H", "-o", "value", "guid", pool], text=True
            ).strip()
            != guid
        ):
            raise ValueError(f"Unexpected pool: {pool}")
    marker = subprocess.check_output(
        ["zfs", "get", "-H", "-o", "value", "org.ansiblonomicon:layout", copy.dataset],
        text=True,
    ).strip()
    if marker != "fresh-v1":
        raise ValueError("Destination is not a prepared fresh dataset")
    if copy.target.is_symlink():
        raise ValueError("The destination must not be a symlink")
    for path, expected in (
        (copy.source, copy.source_dataset),
        (copy.target if copy.target.exists() else copy.target.parent, copy.dataset),
    ):
        mounted = subprocess.check_output(
            ["findmnt", "-n", "-o", "SOURCE", "-T", str(path)], text=True
        ).strip()
        if path.is_symlink() or mounted != expected:
            raise ValueError(f"Unexpected mount for {path}")
    readonly = subprocess.check_output(
        ["zfs", "get", "-H", "-o", "value", "readonly", copy.source_dataset], text=True
    ).strip()
    if readonly != "on":
        raise ValueError("The migration source must be read-only")
    if args.operation == "copy":
        verified = subprocess.check_output(
            [
                "zfs",
                "get",
                "-H",
                "-o",
                "value",
                "org.ansiblonomicon:migration",
                copy.dataset,
            ],
            text=True,
        ).strip()
        if verified != "pending":
            raise ValueError("Refusing to copy into a verified dataset")
        logical = preflight(args.group, copy)
        pool = copy.dataset.split("/")[0]
        before = int(
            subprocess.check_output(
                ["zpool", "get", "-Hp", "-o", "value", "bclonesaved", pool], text=True
            )
        )
        allocated = int(
            subprocess.check_output(
                ["zpool", "get", "-Hp", "-o", "value", "allocated", pool], text=True
            )
        )
        command = [
            "cp",
            "--recursive",
            "--no-dereference",
            "--preserve=mode,ownership,timestamps,links,xattr",
            "--one-file-system",
            "--reflink=auto",
            "--update=none-fail",
        ]
        if args.group == "anypod":
            children = [
                str(path.relative_to(copy.source))
                for path in sorted(copy.source.iterdir())
                if path.name != "data"
            ]
            children += [
                str(path.relative_to(copy.source))
                for path in sorted((copy.source / "data").iterdir())
                if path.name != "db"
            ]
            subprocess.run(
                [*command, "--parents", "--", *children, str(copy.target)],
                cwd=copy.source,
                check=True,
            )
        else:
            sources = (
                [str(source) for source, _target in mappings(args.group, copy)]
                if args.group == "media"
                else [str(copy.source) + "/."]
            )
            copy.target.mkdir(exist_ok=True)
            subprocess.run([*command, "--", *sources, str(copy.target)], check=True)
        subprocess.run(["zpool", "sync", pool], check=True)
        after = int(
            subprocess.check_output(
                ["zpool", "get", "-Hp", "-o", "value", "bclonesaved", pool], text=True
            )
        )
        current_allocated = int(
            subprocess.check_output(
                ["zpool", "get", "-Hp", "-o", "value", "allocated", pool], text=True
            )
        )
        print(
            f"{args.group}: cloned-saved delta {after - before}, pool-allocation delta {current_allocated - allocated}, unique logical bytes {logical}",
            flush=True,
        )
        normalize(args.group, copy)
    verify(args.group, copy)


if __name__ == "__main__":
    main()
