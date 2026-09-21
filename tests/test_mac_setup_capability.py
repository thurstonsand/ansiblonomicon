import ast
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import zipfile

import pytest
from test_software_capability import (
    SOFTWARE,
    executable,
    file_snapshot,
    isolated as isolated,
    run,
)

FONT_NAMES = (
    "BerkeleyMonoNerdFontMono-Regular.otf",
    "BerkeleyMonoNerdFontMono-Bold.otf",
    "BerkeleyMonoNerdFontMono-Oblique.otf",
    "BerkeleyMonoNerdFontMono-BoldOblique.otf",
)


@pytest.mark.parametrize("helper", ["berkeley_mono.py", "docker_context.py"])
def test_software_helpers_support_system_python_39_grammar(helper: str) -> None:
    ast.parse((SOFTWARE / helper).read_text(), feature_version=(3, 9))


def font_archive(path: Path, names: tuple[str, ...] = FONT_NAMES) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        for index, name in enumerate(names):
            signature = b"OTTO" if index % 2 == 0 else b"\x00\x01\x00\x00"
            archive.writestr(name, signature + f"payload:{name}".encode())


def test_berkeley_mono_public_task_check_apply_partial_and_repeat(
    isolated: tuple[dict[str, str], Path, Path, Path, Path], tmp_path: Path
) -> None:
    env, fakebin, _, personal, _ = isolated
    archive = tmp_path / "font.zip"
    font_archive(archive)
    executable(
        fakebin / "op",
        'echo "${OP_SERVICE_ACCOUNT_TOKEN-unset}:${OP_CONNECT_HOST-unset}:${OP_CONNECT_TOKEN-unset}:$*" >> "$HOME/op-calls"\ncat "$FONT_ARCHIVE"',
    )
    fonts = Path(env["HOME"]) / "Library/Fonts"
    fonts.mkdir(parents=True)
    preserved = fonts / FONT_NAMES[0]
    preserved.write_bytes(b"custom")
    preserved_mode = preserved.stat().st_mode & 0o777
    check = run(
        str(personal / "software/reconcile"),
        "berkeley-mono",
        str(personal),
        "check",
        env={**env, "FONT_ARCHIVE": str(archive), "OP_SERVICE_ACCOUNT_TOKEN": "bad"},
    )
    assert check.returncode == 0, check.stderr
    assert not (Path(env["HOME"]) / "op-calls").exists()
    assert sorted(path.name for path in fonts.iterdir()) == [FONT_NAMES[0]]

    apply_env = {**env, "FONT_ARCHIVE": str(archive), "OP_SERVICE_ACCOUNT_TOKEN": "bad"}
    applied = run(
        str(personal / "software/reconcile"),
        "berkeley-mono",
        str(personal),
        "apply",
        env=apply_env,
    )
    assert applied.returncode == 0, applied.stderr
    assert preserved.read_bytes() == b"custom"
    assert {
        path.name: (path.read_bytes(), path.stat().st_mode & 0o777)
        for path in fonts.iterdir()
    } == {
        FONT_NAMES[0]: (b"custom", preserved_mode),
        **{
            name: (
                (b"OTTO" if index % 2 == 0 else b"\x00\x01\x00\x00")
                + f"payload:{name}".encode(),
                0o644,
            )
            for index, name in enumerate(FONT_NAMES[1:], start=1)
        },
    }
    before = file_snapshot(fonts)
    repeated = run(
        str(personal / "software/reconcile"),
        "berkeley-mono",
        str(personal),
        "apply",
        env=apply_env,
    )
    assert repeated.returncode == 0, repeated.stderr
    assert file_snapshot(fonts) == before
    calls = (Path(env["HOME"]) / "op-calls").read_text().splitlines()
    assert calls == [
        "unset:unset:unset:read op://Private/Berkeley Mono Font/nerd-font "
        "--account PQ7X5W7V6FDADHPFFEO62TLFEM"
    ]


@pytest.mark.parametrize("provider_failure", [False, True])
def test_berkeley_mono_bad_archive_or_provider_failure_touches_no_fonts(
    isolated: tuple[dict[str, str], Path, Path, Path, Path],
    tmp_path: Path,
    provider_failure: bool,
) -> None:
    env, fakebin, _, personal, _ = isolated
    archive = tmp_path / "font.zip"
    font_archive(archive, FONT_NAMES[:-1])
    executable(
        fakebin / "op",
        ("exit 19" if provider_failure else 'cat "$FONT_ARCHIVE"'),
    )
    result = run(
        str(personal / "software/reconcile"),
        "berkeley-mono",
        str(personal),
        "apply",
        env={**env, "FONT_ARCHIVE": str(archive)},
    )
    assert result.returncode != 0
    assert not (Path(env["HOME"]) / "Library/Fonts").exists()


def test_berkeley_mono_rejects_directory_destination_before_provider(
    isolated: tuple[dict[str, str], Path, Path, Path, Path],
) -> None:
    env, fakebin, _, personal, _ = isolated
    conflict = Path(env["HOME"]) / "Library/Fonts" / FONT_NAMES[0]
    conflict.mkdir(parents=True)
    executable(fakebin / "op", 'touch "$HOME/op-called"')

    result = run(
        str(personal / "software/reconcile"),
        "berkeley-mono",
        str(personal),
        "apply",
        env=env,
    )

    assert result.returncode != 0
    assert "not a regular file" in result.stderr
    assert not (Path(env["HOME"]) / "op-called").exists()


def test_berkeley_mono_rejects_nonempty_malformed_font_payloads(
    isolated: tuple[dict[str, str], Path, Path, Path, Path], tmp_path: Path
) -> None:
    env, fakebin, _, personal, _ = isolated
    archive = tmp_path / "font.zip"
    with zipfile.ZipFile(archive, "w") as payload:
        for name in FONT_NAMES[:-1]:
            payload.writestr(name, b"OTTOvalid fixture")
        payload.writestr(FONT_NAMES[-1], b"definitely not a font")
    executable(fakebin / "op", 'cat "$FONT_ARCHIVE"')

    result = run(
        str(personal / "software/reconcile"),
        "berkeley-mono",
        str(personal),
        "apply",
        env={**env, "FONT_ARCHIVE": str(archive)},
    )

    assert result.returncode != 0
    assert "invalid expected OpenType font" in result.stderr
    assert not (Path(env["HOME"]) / "Library/Fonts").exists()


def test_berkeley_mono_atomic_create_preserves_concurrent_regular_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    spec = importlib.util.spec_from_file_location(
        "berkeley_mono", SOFTWARE / "berkeley_mono.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    archive = tmp_path / "font.zip"
    font_archive(archive)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(sys, "argv", ["berkeley_mono.py"])

    def provider(*args: object, **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        del args, kwargs
        return subprocess.CompletedProcess(["op"], 0, archive.read_bytes())

    monkeypatch.setattr(module.subprocess, "run", provider)
    real_link = os.link
    raced = False

    def racing_link(source: str, destination: Path) -> None:
        nonlocal raced
        if not raced:
            raced = True
            destination.write_bytes(b"concurrent winner")
            raise FileExistsError
        real_link(source, destination)

    monkeypatch.setattr(module.os, "link", racing_link)

    assert module.main() == 0
    fonts = tmp_path / "Library/Fonts"
    assert (fonts / FONT_NAMES[0]).read_bytes() == b"concurrent winner"
    assert not list(fonts.glob(".*"))


def test_docker_context_public_task_mutates_state_then_converges_and_ignores_env(
    isolated: tuple[dict[str, str], Path, Path, Path, Path],
) -> None:
    env, fakebin, _, personal, _ = isolated
    executable(
        fakebin / "docker",
        r"""state="$HOME/docker-state"
log="$HOME/docker-mutations"
case "$1:$2" in
  context:inspect)
    python3 - "$state" "$3" <<'PY'
import json, pathlib, sys
s=json.loads(pathlib.Path(sys.argv[1]).read_text())
item=s["contexts"].get(sys.argv[2])
if item is None: raise SystemExit(1)
print(json.dumps([item]))
PY
    ;;
  context:ls) python3 - "$state" <<'PY'
import json, pathlib, sys
print("\n".join(json.loads(pathlib.Path(sys.argv[1]).read_text())["contexts"]))
PY
    ;;
  context:show) python3 - "$state" <<'PY'
import json, pathlib, sys
print(json.loads(pathlib.Path(sys.argv[1]).read_text())["current"])
PY
    ;;
  context:create|context:update)
    echo "$2" >> "$log"
    python3 - "$state" "$@" <<'PY'
import json, pathlib, sys
p=pathlib.Path(sys.argv[1]); args=sys.argv[2:]; s=json.loads(p.read_text())
name=args[2]
description=args[args.index("--description") + 1]
docker=args[args.index("--docker") + 1]
if not docker.startswith("host="): raise SystemExit(91)
item=s["contexts"].setdefault(name, {"Name":name,"Metadata":{},"Endpoints":{}})
item["Metadata"]["Description"]=description
item["Endpoints"].setdefault("docker", {})["Host"]=docker.removeprefix("host=")
p.write_text(json.dumps(s))
PY
    ;;
  context:use) echo use >> "$log"; python3 - "$state" "$3" <<'PY'
import json, pathlib, sys
p=pathlib.Path(sys.argv[1]); s=json.loads(p.read_text()); s["current"]=sys.argv[2]; p.write_text(json.dumps(s))
PY
    ;;
  *) exit 90 ;;
esac""",
    )
    state = Path(env["HOME"]) / "docker-state"
    state.write_text(
        '{"current":"default","contexts":{"unrelated":{"Metadata":{"Description":"keep"}}}}'
    )
    task_env = {**env, "DOCKER_HOST": "tcp://override", "DOCKER_CONTEXT": "override"}
    checked = run(
        str(personal / "software/reconcile"),
        "docker-context",
        str(personal),
        "check",
        env=task_env,
    )
    assert checked.returncode == 0, checked.stderr
    assert json.loads(state.read_text())["current"] == "default"
    assert not (Path(env["HOME"]) / "docker-mutations").exists()
    applied = run(
        str(personal / "software/reconcile"),
        "docker-context",
        str(personal),
        "apply",
        env=task_env,
    )
    assert applied.returncode == 0, applied.stderr
    assert json.loads(state.read_text()) == {
        "current": "pod042",
        "contexts": {
            "unrelated": {"Metadata": {"Description": "keep"}},
            "pod042": {
                "Name": "pod042",
                "Metadata": {"Description": "pod042 Debian NAS over SSH"},
                "Endpoints": {"docker": {"Host": "ssh://pod042"}},
            },
        },
    }
    changed = json.loads(state.read_text())
    changed["contexts"]["pod042"]["Endpoints"]["docker"]["Host"] = "ssh://old"
    changed["contexts"]["pod042"]["Metadata"]["x-owner"] = {"team": "personal"}
    changed["contexts"]["pod042"]["Endpoints"]["docker"]["SkipTLSVerify"] = True
    changed["contexts"]["pod042"]["Endpoints"]["metrics"] = {"Host": "tcp://metrics"}
    state.write_text(json.dumps(changed))
    updated = run(
        str(personal / "software/reconcile"),
        "docker-context",
        str(personal),
        "apply",
        env=task_env,
    )
    assert updated.returncode == 0, updated.stderr
    assert json.loads(state.read_text())["contexts"]["pod042"] == {
        "Name": "pod042",
        "Metadata": {
            "Description": "pod042 Debian NAS over SSH",
            "x-owner": {"team": "personal"},
        },
        "Endpoints": {
            "docker": {"Host": "ssh://pod042", "SkipTLSVerify": True},
            "metrics": {"Host": "tcp://metrics"},
        },
    }
    before = state.stat().st_mtime_ns
    repeated = run(
        str(personal / "software/reconcile"),
        "docker-context",
        str(personal),
        "apply",
        env=task_env,
    )
    assert repeated.returncode == 0, repeated.stderr
    assert state.stat().st_mtime_ns == before
    assert (Path(env["HOME"]) / "docker-mutations").read_text() == (
        "create\nuse\nupdate\n"
    )


def test_docker_context_inspect_failure_for_existing_context_fails_without_create(
    isolated: tuple[dict[str, str], Path, Path, Path, Path],
) -> None:
    env, fakebin, _, personal, _ = isolated
    executable(
        fakebin / "docker",
        'case "$1:$2" in context:inspect) echo denied >&2; exit 17;; context:ls) echo pod042;; *) echo mutation > "$HOME/mutation";; esac',
    )
    result = run(
        str(personal / "software/reconcile"),
        "docker-context",
        str(personal),
        "apply",
        env=env,
    )
    assert result.returncode == 17
    assert "denied" in result.stderr
    assert not (Path(env["HOME"]) / "mutation").exists()


@pytest.mark.parametrize(
    "response",
    [
        "{}",
        "[]",
        "[{}, {}]",
        '[{"Name":"other","Metadata":{},"Endpoints":{}}]',
        '[{"Name":"pod042","Metadata":[],"Endpoints":{}}]',
        '[{"Name":"pod042","Metadata":{},"Endpoints":[]}]',
        '[{"Name":"pod042","Metadata":{},"Endpoints":{"docker":[]}}]',
    ],
)
def test_docker_context_cli_rejects_malformed_inspect_without_mutation(
    isolated: tuple[dict[str, str], Path, Path, Path, Path], response: str
) -> None:
    env, fakebin, _, personal, _ = isolated
    executable(
        fakebin / "docker",
        'if [ "$1:$2" = context:inspect ]; then printf %s "$BAD_RESPONSE"; else touch "$HOME/mutation"; fi',
    )

    result = run(
        str(personal / "software/reconcile"),
        "docker-context",
        str(personal),
        "apply",
        env={**env, "BAD_RESPONSE": response},
    )

    assert result.returncode != 0
    assert "invalid context data" in result.stderr
    assert not (Path(env["HOME"]) / "mutation").exists()


def test_docker_context_missing_prerequisite_fails_clearly(
    isolated: tuple[dict[str, str], Path, Path, Path, Path],
) -> None:
    env, fakebin, _, personal, _ = isolated
    result = run(
        sys.executable,
        str(personal / "software/docker_context.py"),
        "--check",
        env={**env, "PATH": str(fakebin)},
    )
    assert result.returncode != 0
    assert "docker is required" in result.stderr
