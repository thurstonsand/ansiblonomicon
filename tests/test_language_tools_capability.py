import json
import os
from pathlib import Path
import subprocess
import sys
import time
import tomllib

ROOT = Path(__file__).resolve().parents[1]
RECONCILE = ROOT / "bootstrap/capabilities/language-tools/reconcile.py"
NPM_GLOBALS = ROOT / "bootstrap/capabilities/language-tools/npm-globals.py"
INSTALL = ROOT / "bootstrap/capabilities/mise/install"


def executable(path: Path, body: str) -> None:
    path.write_text("#!/bin/sh\nset -eu\n" + body)
    path.chmod(0o755)


def clean_environment(home: Path, path: str) -> dict[str, str]:
    return {
        "HOME": str(home),
        "PATH": path,
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
    }


def fixture(
    tmp_path: Path, *, scalar: bool = False, fail: str = ""
) -> tuple[dict[str, str], Path]:
    home = tmp_path / "home"
    config = home / ".config/mise/config.toml"
    config.parent.mkdir(parents=True)
    config.write_text(
        (
            '[tools]\nnode = "20"\n'
            if scalar
            else '[tools.node]\nversion = "20"\nunknown = "keep"\n'
            "[tools.node.options]\ncompile = true\n"
        )
        + '[tools.python]\nversion = "3.13"\n'
    )
    fake = tmp_path / "fake-bin"
    old = tmp_path / "old-node/bin"
    new = tmp_path / "new-node/bin"
    # Homebrew's node precedes mise's in the inherited PATH on the work Mac.
    shadow = tmp_path / "shadow-node/bin"
    for directory in (fake, old, new, shadow):
        directory.mkdir(parents=True)
    executable(shadow / "npm", 'echo "npm[shadow] $*" >> "$CALLS"; exit 97\n')
    (fake / "python3").symlink_to(sys.executable)
    calls = tmp_path / "calls"
    packages = tmp_path / "npm-packages"
    old_packages = tmp_path / "npm-packages-old"
    packages.write_text("unmanaged-extra\n")
    old_packages.write_text("unmanaged-extra@1.2.3\nnpm@11.0.0\ncorepack@0.30.0\n")
    npmrc = home / ".npmrc"
    npmrc.write_text(
        "//registry.example/:_authToken=keep-this-secret\nallow-scripts=old-policy\n"
    )
    npm_body = r"""echo "npm[$NPM_ID] $*" >> "$CALLS"
if [ "$1 $2" = "prefix -g" ]; then dirname "$(dirname "$0")"; exit 0; fi
if [ "$1 $2" = "root -g" ]; then printf '%s/lib/node_modules\n' "$(dirname "$(dirname "$0")")"; exit 0; fi
if [ "$1" = list ] && printf '%s\n' "$*" | grep -q -- '--json'; then
  printf '{"dependencies":{'; sep=
  while IFS= read -r package; do
    [ -n "$package" ] || continue
    case "$package" in LINK:*) name=${package#LINK:}; printf '%s"%s":{"version":"1.0.0","link":true}' "$sep" "$name"; sep=,; continue;; esac
    name=${package%@*}; version=${package##*@}
    printf '%s"%s":{"version":"%s"}' "$sep" "$name" "$version"; sep=,
  done < "$NPM_PACKAGES"
  printf '}}\n'; exit 0
fi
if [ "$1 $2 $3" = "config get allow-scripts" ]; then
  sed -n 's/^allow-scripts=//p' "$NPMRC" | tail -1
  exit 0
fi
if [ "$1 $2" = "config set" ]; then
  value=${3#allow-scripts=}
  grep -v '^allow-scripts=' "$NPMRC" > "$NPMRC.tmp" || true
  printf 'allow-scripts=%s\n' "$value" >> "$NPMRC.tmp"
  mv "$NPMRC.tmp" "$NPMRC"
  exit 0
fi
if [ "$1" = list ]; then grep -Eq "^$5(@|$)" "$NPM_PACKAGES"; exit; fi
if [ "$1" = install ]; then
  [ "${FAIL:-}" != npm ] || exit 19
  for package in "$@"; do
    case "$package" in install|-g|--allow-scripts=*|--prefix) ;; "$NEW_PREFIX") ;; *) grep -Fxq "$package" "$NPM_PACKAGES" || echo "$package" >> "$NPM_PACKAGES";; esac
  done
fi
"""
    for directory, identity in ((old, "old"), (new, "new")):
        executable(directory / "npm", f"NPM_ID={identity}; export NPM_ID\n" + npm_body)
        npm_cli = directory.parent / "lib/node_modules/npm/bin/npm-cli.js"
        npm_cli.parent.mkdir(parents=True)
        npm_cli.write_text("")
        executable(
            directory / "node",
            f'NPM_ID={identity}; export NPM_ID\nNPM_PACKAGES="$NPM_PACKAGES_{identity.upper()}"; export NPM_PACKAGES\nshift\nexec "{directory / "npm"}" "$@"\n',
        )
    executable(
        fake / "mise",
        'echo "mise $*" >> "$CALLS"\n'
        'if [ "$1" = config ] || [ "$1" = trust ]; then exec "$REAL_MISE" "$@"; fi\n'
        '[ "$1" != install ] || [ "${FAIL:-}" != install ] || exit 17\n'
        '[ "$1" != upgrade ] || [ "${FAIL:-}" != upgrade ] || exit 18\n'
        'if [ "$1 ${2:-} ${3:-} ${4:-}" = "ls --current --json node" ]; then printf \'[{"version":"20.0.0","install_path":"%s","installed":true,"active":true}]\\n\' "$OLD_PREFIX"; fi\n'
        'if [ "$1 $2" = "env --json" ]; then printf \'{"PATH":"%s:%s:/usr/bin:/bin"}\\n\' "$SHADOW_BIN" "$FAKE_BIN"; fi\n'
        'if [ "$1 $2" = "which npm" ]; then printf \'%s/npm\\n\' "$NEW_BIN"; fi\n',
    )
    executable(
        fake / "uv",
        'echo "uv $*" >> "$CALLS"\n[ "$1 $2" != "tool dir" ] || printf "%s\\n" "$UV_DIR"\n',
    )
    executable(fake / "go", 'echo "go $*" >> "$CALLS"\n')
    for command in ("bun", "rustup", "cargo", "gem"):
        executable(fake / command, f'echo "{command} $*" >> "$CALLS"\n')
    env = clean_environment(home, f"{old}:{fake}:/usr/bin:/bin")
    env.update(
        {
            "MISE_BIN": str(fake / "mise"),
            "REAL_MISE": subprocess.check_output(["which", "mise"], text=True).strip(),
            "NEW_BIN": str(new),
            "SHADOW_BIN": str(shadow),
            "FAKE_BIN": str(fake),
            "UV_DIR": str(tmp_path / "uv-tools"),
            "CALLS": str(calls),
            "NPMRC": str(npmrc),
            "NPM_PACKAGES": str(packages),
            "NPM_PACKAGES_OLD": str(old_packages),
            "NPM_PACKAGES_NEW": str(packages),
            "OLD_PREFIX": str(old.parent),
            "NEW_PREFIX": str(new.parent),
            "LANGUAGE_TOOLS_GEM": str(fake / "gem"),
            "FAIL": fail,
        }
    )
    return env, calls


def run_reconcile(
    env: dict[str, str], *arguments: str, check: bool = True
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["python3", str(RECONCILE), "--profile", "personal", *arguments],
        env=env,
        check=check,
        text=True,
        capture_output=True,
    )


def test_node_upgrade_carries_user_globals_and_preserves_foreign_config(
    tmp_path: Path,
) -> None:
    env, calls = fixture(tmp_path)
    run_reconcile(env)
    config = tomllib.loads((Path(env["HOME"]) / ".config/mise/config.toml").read_text())
    assert config["tools"]["node"]["unknown"] == "keep"
    assert config["tools"]["node"]["options"] == {"compile": True}
    assert config["tools"]["python"] == {"version": "3.13"}
    output = calls.read_text()
    assert "mise exec" not in output
    assert "npm[old] install" not in output
    # Globals the user installed by hand follow node across the upgrade; the ones
    # node bundles itself must not be pinned back to the old node's versions.
    assert "unmanaged-extra@1.2.3" in output
    assert "npm@11.0.0" not in output
    assert "corepack@0.30.0" not in output
    assert "keep-this-secret" in Path(env["NPMRC"]).read_text()


def test_postinstall_uses_new_nodes_bundled_npm_despite_old_initial_path(
    tmp_path: Path,
) -> None:
    env, calls = fixture(tmp_path)
    extension = tmp_path / "postinstall-only.toml"
    extension.write_text('[npm]\npackages = ["extension-package"]\n')
    run_reconcile(env, "--extension", str(extension))
    config = tomllib.loads((Path(env["HOME"]) / ".config/mise/config.toml").read_text())
    hook = config["tools"]["node"]["postinstall"]
    assert "python" not in hook
    assert str(ROOT) not in hook
    extension.unlink()
    calls.write_text("")
    hook_env = dict(env)
    hook_env["MISE_TOOL_INSTALL_PATH"] = str(Path(env["NEW_BIN"]).parent)
    subprocess.run(["sh", "-c", hook], env=hook_env, check=True)
    assert "npm[new]" in calls.read_text()
    assert "npm[old]" not in calls.read_text()
    assert "extension-package" in Path(env["NPM_PACKAGES"]).read_text().splitlines()


def test_missing_npm_package_is_restored_when_upgrades_not_due(tmp_path: Path) -> None:
    env, calls = fixture(tmp_path)
    run_reconcile(env)
    package_file = Path(env["NPM_PACKAGES"])
    package_file.write_text("unmanaged-extra\n")
    calls.write_text("")
    run_reconcile(env)
    assert "npm[new] install -g" in calls.read_text()
    assert "unmanaged-extra" in package_file.read_text().splitlines()
    assert "agent-browser" in package_file.read_text().splitlines()
    assert "mise upgrade" not in calls.read_text()


def test_npm_helper_retains_interpreter_when_global_path_changes(
    tmp_path: Path,
) -> None:
    env, calls = fixture(tmp_path)
    executable(Path(env["NEW_BIN"]) / "python3", "exit 88\n")
    run_reconcile(env)
    assert "npm[new] install -g" in calls.read_text()
    assert "tuistory" in Path(env["NPM_PACKAGES"]).read_text().splitlines()
    assert (Path(env["HOME"]) / ".cache/ansiblonomicon/language-tools.stamp").exists()


def test_real_mise_parser_adopts_scalar_and_preserves_other_tools(
    tmp_path: Path,
) -> None:
    env, _ = fixture(tmp_path, scalar=True)
    run_reconcile(env)
    config = tomllib.loads((Path(env["HOME"]) / ".config/mise/config.toml").read_text())
    assert config["tools"]["node"]["version"] == "lts"
    assert config["tools"]["python"] == {"version": "3.13"}
    assert "postinstall" in config["tools"]["node"]


def test_check_is_read_only_and_environment_is_clean(tmp_path: Path) -> None:
    env, calls = fixture(tmp_path)
    before = (Path(env["HOME"]) / ".config/mise/config.toml").read_bytes()
    result = run_reconcile(env, "--check")
    assert not calls.exists()
    assert (Path(env["HOME"]) / ".config/mise/config.toml").read_bytes() == before
    assert "ensure installed node@lts" in result.stdout


def test_typed_invalid_inventory_writes_neither_config_nor_stamp(
    tmp_path: Path,
) -> None:
    env, calls = fixture(tmp_path)
    config = Path(env["HOME"]) / ".config/mise/config.toml"
    before = config.read_bytes()
    extension = tmp_path / "bad.toml"
    extension.write_text('[npm]\npackages = "not-an-array"\n')
    result = run_reconcile(env, "--extension", str(extension), check=False)
    assert result.returncode != 0
    assert config.read_bytes() == before
    assert not calls.exists()
    assert not (
        Path(env["HOME"]) / ".cache/ansiblonomicon/language-tools.stamp"
    ).exists()


def test_unsupported_tool_lists_and_literal_dot_keys_fail_before_writes(
    tmp_path: Path,
) -> None:
    for name, body, message in (
        (
            "list",
            '[tools.node]\nversion = "lts"\noption = ["a,b", true]\n',
            "list value",
        ),
        (
            "dot",
            '[tools."literal.name"]\nversion = "latest"\n',
            "tool names containing dots",
        ),
        (
            "nested-dot",
            '[tools.node]\nversion = "lts"\n"literal.option" = true\n',
            "literal-dot key",
        ),
    ):
        env, calls = fixture(tmp_path / name)
        config = Path(env["HOME"]) / ".config/mise/config.toml"
        before = config.read_bytes()
        extension = tmp_path / name / "unsupported.toml"
        extension.write_text(body)
        result = run_reconcile(env, "--extension", str(extension), check=False)
        assert result.returncode != 0
        assert message in result.stderr
        assert config.read_bytes() == before
        assert not calls.exists()


def test_scalar_and_nested_table_options_use_real_mise_parser(tmp_path: Path) -> None:
    env, _ = fixture(tmp_path)
    extension = tmp_path / "options.toml"
    extension.write_text(
        '[tools.node]\nversion = "lts"\n'
        '[tools.node.options]\ncompile = false\njobs = 4\nratio = 1.5\nlabel = "a,b"\n'
    )
    run_reconcile(env, "--extension", str(extension))
    config = tomllib.loads((Path(env["HOME"]) / ".config/mise/config.toml").read_text())
    assert config["tools"]["node"]["options"] == {
        "compile": False,
        "jobs": 4,
        "ratio": 1.5,
        "label": "a,b",
    }


def test_fingerprint_and_exact_due_boundary(tmp_path: Path) -> None:
    env, calls = fixture(tmp_path)
    run_reconcile(env)
    stamp = Path(env["HOME"]) / ".cache/ansiblonomicon/language-tools.stamp"
    original = stamp.read_text()
    calls.write_text("")
    run_reconcile(env)
    assert "mise upgrade" not in calls.read_text()
    os.utime(stamp, (time.time() - 86400, time.time() - 86400))
    calls.write_text("")
    run_reconcile(env)
    assert "mise upgrade --yes --no-prune" in calls.read_text()
    assert stamp.read_text() == original
    stamp.write_text("different-inventory-fingerprint\n")
    calls.write_text("")
    run_reconcile(env)
    assert "mise upgrade --yes --no-prune" in calls.read_text()
    assert stamp.read_text() == original


def test_install_and_upgrade_failures_preserve_existing_stamp(tmp_path: Path) -> None:
    for failure in ("install", "upgrade"):
        env, _ = fixture(tmp_path / failure, fail=failure)
        stamp = Path(env["HOME"]) / ".cache/ansiblonomicon/language-tools.stamp"
        stamp.parent.mkdir(parents=True)
        stamp.write_text("existing metadata\n")
        result = run_reconcile(env, check=False)
        assert result.returncode != 0
        assert stamp.read_text() == "existing metadata\n"


def test_pending_npm_snapshot_survives_install_failure_and_retry(
    tmp_path: Path,
) -> None:
    env, calls = fixture(tmp_path, fail="install")
    result = run_reconcile(env, check=False)
    assert result.returncode != 0
    pending = Path(env["HOME"]) / ".cache/ansiblonomicon/npm-globals.pending.json"
    assert pending.stat().st_mode & 0o777 == 0o600
    assert json.loads(pending.read_text()) == {"unmanaged-extra": "1.2.3"}

    calls.write_text("")
    retry_env = dict(env)
    retry_env["FAIL"] = ""
    run_reconcile(retry_env)
    assert "npm[old] list" not in calls.read_text()
    assert "unmanaged-extra@1.2.3" in calls.read_text()
    assert not pending.exists()


def test_unsupported_npm_source_fails_before_config_or_runtime_writes(
    tmp_path: Path,
) -> None:
    env, calls = fixture(tmp_path)
    Path(env["NPM_PACKAGES_OLD"]).write_text("LINK:local-tool\n")
    config = Path(env["HOME"]) / ".config/mise/config.toml"
    before = config.read_bytes()
    result = run_reconcile(env, check=False)
    assert result.returncode != 0
    assert "unsupported npm global source for local-tool" in result.stderr
    assert config.read_bytes() == before
    output = calls.read_text()
    assert "mise config" not in output
    assert "mise install" not in output
    assert "mise upgrade" not in output


def test_linked_npm_global_is_preserved_and_relinked_into_new_node(
    tmp_path: Path,
) -> None:
    env, calls = fixture(tmp_path)
    Path(env["NPM_PACKAGES_OLD"]).write_text("LINK:linked-tool\n")
    clone = Path(env["HOME"]) / "clones/linked-tool"
    clone.mkdir(parents=True)
    extension = tmp_path / "links.toml"
    extension.write_text('[npm.links]\nlinked-tool = "clones/linked-tool"\n')
    run_reconcile(env, "--extension", str(extension))
    link = Path(env["NEW_PREFIX"]) / "lib/node_modules/linked-tool"
    assert link.readlink() == clone
    assert "linked-tool" not in calls.read_text()
    before = link.lstat()
    run_reconcile(env, "--extension", str(extension))
    after = link.lstat()
    assert (before.st_ino, before.st_mtime_ns) == (after.st_ino, after.st_mtime_ns)


def test_npm_link_waits_for_absent_target_and_refuses_installed_package(
    tmp_path: Path,
) -> None:
    env, _ = fixture(tmp_path)
    extension = tmp_path / "links.toml"
    extension.write_text('[npm.links]\nlinked-tool = "clones/linked-tool"\n')
    result = run_reconcile(env, "--extension", str(extension))
    link = Path(env["NEW_PREFIX"]) / "lib/node_modules/linked-tool"
    assert not link.exists() and not link.is_symlink()
    assert "stays unlinked" in result.stderr
    (Path(env["HOME"]) / "clones/linked-tool").mkdir(parents=True)
    link.mkdir(parents=True)
    result = run_reconcile(env, "--extension", str(extension), check=False)
    assert result.returncode != 0
    assert "refusing to replace installed npm package" in result.stderr


def test_npm_links_reject_unsafe_targets(tmp_path: Path) -> None:
    env, calls = fixture(tmp_path)
    extension = tmp_path / "links.toml"
    for body in (
        '[npm.links]\ntool = "/abs/path"\n',
        '[npm.links]\ntool = "../escape"\n',
        '[npm.links]\n"bad/name" = "clone"\n',
    ):
        extension.write_text(body)
        result = run_reconcile(env, "--extension", str(extension), check=False)
        assert result.returncode != 0
        assert "npm.links must map package names" in result.stderr
    assert not calls.exists()


def test_npm_failure_preserves_existing_stamp(tmp_path: Path) -> None:
    env, _ = fixture(tmp_path, fail="npm")
    stamp = Path(env["HOME"]) / ".cache/ansiblonomicon/language-tools.stamp"
    stamp.parent.mkdir(parents=True)
    stamp.write_text("existing metadata\n")
    result = run_reconcile(env, check=False)
    assert result.returncode != 0
    assert stamp.read_text() == "existing metadata\n"


def test_repeat_reconcile_preserves_config_npmrc_and_stamp_metadata(
    tmp_path: Path,
) -> None:
    env, _ = fixture(tmp_path)
    run_reconcile(env)
    paths = (
        Path(env["HOME"]) / ".config/mise/config.toml",
        Path(env["NPMRC"]),
        Path(env["HOME"]) / ".cache/ansiblonomicon/language-tools.stamp",
    )
    before = [(path.read_bytes(), path.stat().st_mtime_ns) for path in paths]
    run_reconcile(env)
    assert [(path.read_bytes(), path.stat().st_mtime_ns) for path in paths] == before


def test_work_requires_attestation_and_private_managers(tmp_path: Path) -> None:
    env, calls = fixture(tmp_path)
    result = subprocess.run(["python3", str(RECONCILE), "--profile", "work"], env=env)
    assert result.returncode != 0 and not calls.exists()
    extension = tmp_path / "work.toml"
    extension.write_text(
        '[bun]\npackages=["bun-cli"]\n[cargo]\npackages=["bob-nvim"]\n[gem]\npackages=["ruby-cli"]\n'
    )
    bob = Path(env["HOME"]) / ".cargo/bin/bob"
    bob.parent.mkdir(parents=True)
    executable(bob, 'echo "bob $*" >> "$CALLS"\n')
    subprocess.run(
        ["python3", str(RECONCILE), "--profile", "work", "--extension", str(extension)],
        env=env,
        check=True,
    )
    output = calls.read_text()
    assert "bun install --global bun-cli" in output
    assert "cargo binstall --no-confirm bob-nvim" in output
    assert "bob use stable" in output
    assert "gem install ruby-cli" in output


def installer_fixture(
    tmp_path: Path, curl_body: str
) -> tuple[dict[str, str], Path, Path]:
    home = tmp_path / "home"
    fake = tmp_path / "bin"
    home.mkdir()
    fake.mkdir()
    executable(fake / "curl", curl_body)
    env = clean_environment(home, f"{fake}:/usr/bin:/bin")
    return env, home, tmp_path / "target/mise"


def test_standalone_installer_executes_downloaded_helper_without_home_writes(
    tmp_path: Path,
) -> None:
    env, home, target = installer_fixture(
        tmp_path,
        'out=\nwhile [ $# -gt 0 ]; do [ "$1" != -o ] || { shift; out=$1; }; shift; done\n'
        'printf \'#!/bin/sh\\nset -eu\\nprintf installed > "$MISE_INSTALL_PATH"\\nchmod +x "$MISE_INSTALL_PATH"\\n\' > "$out"\n',
    )
    subprocess.run([str(INSTALL), str(target)], env=env, check=True)
    assert target.read_text() == "installed"
    assert list(home.iterdir()) == []


def test_standalone_download_failure_is_failure_and_leaves_no_home_state(
    tmp_path: Path,
) -> None:
    env, home, target = installer_fixture(tmp_path, "exit 22\n")
    result = subprocess.run([str(INSTALL), str(target)], env=env)
    assert result.returncode != 0
    assert not target.exists()
    assert list(home.iterdir()) == []


def test_standalone_existing_binary_is_untouched(tmp_path: Path) -> None:
    env, _, target = installer_fixture(tmp_path, "exit 99\n")
    target.parent.mkdir()
    executable(target, "exit 0\n")
    before = (target.read_bytes(), target.stat().st_mode, target.stat().st_mtime_ns)
    subprocess.run([str(INSTALL), str(target)], env=env, check=True)
    assert (
        target.read_bytes(),
        target.stat().st_mode,
        target.stat().st_mtime_ns,
    ) == before
