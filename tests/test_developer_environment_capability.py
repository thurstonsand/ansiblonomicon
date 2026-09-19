import configparser
import os
from pathlib import Path
import shutil
import subprocess
import tomllib

import pytest

ROOT = Path(__file__).resolve().parents[1]
NVIM = ROOT / "bootstrap/capabilities/neovim"
PYTHON_INDEX = ROOT / "bootstrap/capabilities/python-index"
HOSTS = ("pod042", "Thurstons-MacBook-Pro", "ML-DFC6YK6VJQ")


def fixture_target(
    tmp_path: Path, host: str, *, work_values: bool = False
) -> tuple[Path, Path, dict[str, str]]:
    target = tmp_path / "targets/fixture"
    home = tmp_path / "home"
    target.mkdir(parents=True)
    home.mkdir()
    registered = ROOT / "bootstrap/targets" / host
    shutil.copy(registered / "mise.toml", target / "mise.toml")
    shutil.copy(NVIM / "mise.toml", target / "mise.neovim.toml")
    profile = "work" if host == "ML-DFC6YK6VJQ" else "personal"
    shutil.copy(NVIM / f"mise.{profile}.toml", target / f"mise.neovim-{profile}.toml")
    source = tmp_path / "sources/neovim"
    shutil.copytree(NVIM / "files", source)
    (target / "neovim").symlink_to(source, target_is_directory=True)
    environments = f"neovim,neovim-{profile}"
    if work_values:
        shutil.copy(PYTHON_INDEX / "mise.toml", target / "mise.python-index.toml")
        (target / "python-index").symlink_to(
            PYTHON_INDEX / "files", target_is_directory=True
        )
        (target / "mise.local.toml").write_text(
            """[vars]
neovim_jira_browse_url = "https://jira.example/a'b/"
neovim_scm_remote_patterns = '''        { "^ssh://x/(.*)$", "https://example/%1" },'''
neovim_scm_url_patterns = '''        ["git%.example"] = {
          branch = "/b/{branch}",
          file = "/f/{file}#L{line_start}",
        },'''
python_index_config = '''index-strategy = "unsafe-best-match"
[[index]]
url = "https://default.example/simple"
default = true
name = "default"
[[index]]
url = "https://one.example/a&b"
[[index]]
url = 'https://two.example/a\\b'
name = "two"
'''
"""
        )
    env = {
        "PATH": os.environ["PATH"],
        "HOME": str(home),
        "XDG_CACHE_HOME": str(home / ".cache"),
        "XDG_CONFIG_HOME": str(home / ".config"),
        "XDG_DATA_HOME": str(home / ".local/share"),
        "XDG_STATE_HOME": str(home / ".local/state"),
        "MISE_CACHE_DIR": str(home / ".cache/mise"),
        "MISE_CONFIG_DIR": str(home / ".config/mise"),
        "MISE_DATA_DIR": str(home / ".local/share/mise"),
        "MISE_STATE_DIR": str(home / ".local/state/mise"),
        "MISE_SYSTEM_CONFIG_FILE": str(target / "absent-system.toml"),
        "MISE_GLOBAL_CONFIG_FILE": str(target / "absent-global.toml"),
        "MISE_CEILING_PATHS": str(target.parent),
        "MISE_TRUSTED_CONFIG_PATHS": str(target),
        "MISE_ENV": environments,
        "MISE_AUTO_INSTALL": "0",
    }
    return target, home, env


def dotfiles(
    target: Path, env: dict[str, str], *arguments: str
) -> subprocess.CompletedProcess[str]:
    command = [
        "mise",
        "-C",
        str(target),
    ]
    if env.get("MISE_ENV") == "python-index":
        command.extend(["run", "python-index:apply"])
        if "--dry-run" in arguments:
            command.append("--check")
    else:
        command.extend(
            [
                "bootstrap",
                "dotfiles",
                "apply",
                "--force",
                *arguments,
            ]
        )
    result = subprocess.run(
        command,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return result


@pytest.mark.parametrize("host", HOSTS)
def test_hosts_register_neovim_with_the_intended_lock_policy(host: str) -> None:
    target = ROOT / "bootstrap/targets" / host
    profile = "work" if host == "ML-DFC6YK6VJQ" else "personal"
    assert (target / "mise.neovim.toml").resolve() == (NVIM / "mise.toml").resolve()
    assert (target / f"mise.neovim-{profile}.toml").resolve() == (
        NVIM / f"mise.{profile}.toml"
    ).resolve()
    manifest = tomllib.loads((NVIM / f"mise.{profile}.toml").read_text())
    assert manifest["dotfiles"]["~/.config/nvim/lazy-lock.json"]["mode"] == (
        "copy" if profile == "work" else "symlink"
    )
    shared = tomllib.loads((NVIM / "mise.toml").read_text())
    assert shared["tasks"]["neovim:plugins"]["timeout"] == "10m"
    assert shared["tasks"]["neovim:mason"] == {
        **shared["tasks"]["neovim:mason"],
        "depends": ["neovim:plugins"],
        "timeout": "10m",
    }
    assert shared["tasks"]["neovim:setup"] == {
        **shared["tasks"]["neovim:setup"],
        "depends": ["neovim:mason"],
        "timeout": "10m",
    }


@pytest.mark.parametrize("host", HOSTS)
def test_real_neovim_manifests_render_idempotently_and_keep_neighbors(
    host: str, tmp_path: Path
) -> None:
    target, home, env = fixture_target(
        tmp_path, host, work_values=host == "ML-DFC6YK6VJQ"
    )
    neighbor = home / ".config/nvim/local-only.lua"
    neighbor.parent.mkdir(parents=True)
    neighbor.write_text("return 'keep'\n")
    (home / ".config/nvim/init.lua").write_text("-- old chezmoi file\n")
    (home / ".config/nvim/lazy-lock.json").write_text('{"old":true}\n')
    source_lock = tmp_path / "lock-source.json"
    source_lock.write_bytes((NVIM / "files/lazy-lock.json").read_bytes())
    (target / "neovim/lazy-lock.json").unlink()
    (target / "neovim/lazy-lock.json").symlink_to(source_lock)

    preview = dotfiles(target, env, "--dry-run")
    assert "nvim --headless" not in preview.stdout + preview.stderr
    assert (home / ".config/nvim/init.lua").read_text() == "-- old chezmoi file\n"
    assert (home / ".config/nvim/lazy-lock.json").read_text() == '{"old":true}\n'
    dotfiles(target, env, "--yes")

    init = home / ".config/nvim/init.lua"
    lock = home / ".config/nvim/lazy-lock.json"
    jira = home / ".config/nvim/lua/plugins/jira.lua"
    assert init.is_symlink()
    assert neighbor.read_text() == "return 'keep'\n"
    assert lock.is_symlink() is (host != "ML-DFC6YK6VJQ")
    if host == "ML-DFC6YK6VJQ":
        assert "https://jira.example/a'b/" in jira.read_text()
        assert (home / ".config/nvim/lua/plugins/gitbrowse.work.lua").is_file()
    else:
        assert "https://jira.atlassian.com/browse/" in jira.read_text()

    managed = (init, lock, jira)
    before = {
        path: (path.lstat().st_ino, path.lstat().st_mtime_ns, path.lstat().st_ctime_ns)
        for path in managed
    }
    dotfiles(target, env, "--yes")
    assert {
        path: (path.lstat().st_ino, path.lstat().st_mtime_ns, path.lstat().st_ctime_ns)
        for path in managed
    } == before

    lock.write_text('{"fixture":"changed"}\n')
    if host == "ML-DFC6YK6VJQ":
        assert source_lock.read_text() != lock.read_text()
        dotfiles(target, env, "--yes")
        assert lock.read_bytes() == source_lock.read_bytes()
    else:
        assert source_lock.read_text() == '{"fixture":"changed"}\n'


def test_work_python_indexes_render_for_uv_and_pip_without_losing_extras(
    tmp_path: Path,
) -> None:
    target, home, env = fixture_target(tmp_path, "ML-DFC6YK6VJQ", work_values=True)
    env["MISE_ENV"] = "python-index"
    uv = home / ".config/uv/uv.toml"
    pip = home / ".config/pip/pip.conf"
    uv.parent.mkdir(parents=True)
    pip.parent.mkdir(parents=True)
    uv.write_text("old uv\n")
    pip.write_text("old pip\n")
    neighbor = home / ".config/uv/unmanaged.toml"
    neighbor.write_text("keep\n")
    preview = dotfiles(target, env, "--dry-run")
    assert uv.read_text() == "old uv\n"
    assert pip.read_text() == "old pip\n"
    assert preview.returncode == 0
    dotfiles(target, env, "--yes")
    assert neighbor.read_text() == "keep\n"
    rendered_uv = (home / ".config/uv/uv.toml").read_text()
    assert (
        rendered_uv
        == tomllib.loads((target / "mise.local.toml").read_text())["vars"][
            "python_index_config"
        ]
    )
    uv_config = tomllib.loads(rendered_uv)
    assert uv_config == {
        "index": [
            {
                "url": "https://default.example/simple",
                "default": True,
                "name": "default",
            },
            {"url": "https://one.example/a&b"},
            {"url": "https://two.example/a\\b", "name": "two"},
        ],
        "index-strategy": "unsafe-best-match",
    }
    parser = configparser.ConfigParser()
    parser.read(home / ".config/pip/pip.conf")
    assert parser["global"]["index-url"] == "https://default.example/simple"
    assert parser["global"]["extra-index-url"].splitlines() == [
        "https://one.example/a&b",
        "https://two.example/a\\b",
    ]


def test_root_python_index_task_previews_applies_repeats_and_rejects_bad_input(
    tmp_path: Path,
) -> None:
    target, home, env = fixture_target(tmp_path, "ML-DFC6YK6VJQ", work_values=True)
    project = tmp_path / "project"
    registered = project / "bootstrap/targets/ML-DFC6YK6VJQ"
    registered.parent.mkdir(parents=True)
    registered.symlink_to(target, target_is_directory=True)
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    hostname = fake_bin / "hostname"
    hostname.write_text('#!/bin/sh\nprintf "%s\\n" ML-DFC6YK6VJQ\n')
    hostname.chmod(0o755)
    env.update(
        {
            "PATH": f"{fake_bin}:{env['PATH']}",
            "MISE_PROJECT_ROOT": str(project),
        }
    )
    run = tomllib.loads((ROOT / "mise.toml").read_text())["tasks"]["python-index"][
        "run"
    ]
    uv = home / ".config/uv/uv.toml"
    pip = home / ".config/pip/pip.conf"
    uv.parent.mkdir(parents=True)
    pip.parent.mkdir(parents=True)
    uv.write_text("old uv\n")
    pip.write_text("old pip\n")

    preview = subprocess.run(
        ["sh", "-c", run],
        env={**env, "usage_check": "true"},
        check=False,
        capture_output=True,
        text=True,
    )
    assert preview.returncode == 0, preview.stdout + preview.stderr
    assert (uv.read_text(), pip.read_text()) == ("old uv\n", "old pip\n")

    subprocess.run(["sh", "-c", run], env=env, check=True)
    expected = (uv.read_bytes(), pip.read_bytes())
    before = (uv.stat().st_mtime_ns, pip.stat().st_mtime_ns)
    subprocess.run(["sh", "-c", run], env=env, check=True)
    assert (uv.read_bytes(), pip.read_bytes()) == expected
    assert (uv.stat().st_mtime_ns, pip.stat().st_mtime_ns) == before

    local = target / "mise.local.toml"
    local.write_text(
        local.read_text().replace(
            'url = "https://default.example/simple"', 'url = "bad"'
        )
    )
    failed = subprocess.run(
        ["sh", "-c", run], env=env, check=False, capture_output=True, text=True
    )
    assert failed.returncode != 0
    assert "valid HTTP(S) URL" in failed.stderr
    assert (uv.read_bytes(), pip.read_bytes()) == expected


def test_rendered_lua_returns_expected_literal_configuration(tmp_path: Path) -> None:
    if shutil.which("nvim") is None:
        pytest.skip("nvim is unavailable")
    target, home, env = fixture_target(tmp_path, "ML-DFC6YK6VJQ", work_values=True)
    dotfiles(target, env, "--yes")
    script = tmp_path / "assert-config.lua"
    plugins = home / ".config/nvim/lua/plugins"
    script.write_text(f'''local mason = assert(loadfile("{plugins}/mason.lua"))()
assert(mason[1][1] == "mason-org/mason.nvim")
assert(#mason[1].opts.ensure_installed == 0)
local jira = assert(loadfile("{plugins}/jira.lua"))()
assert(jira[1] == "folke/snacks.nvim")
local browse = assert(loadfile("{plugins}/gitbrowse.work.lua"))()
assert(browse.opts.gitbrowse.remote_patterns[#browse.opts.gitbrowse.remote_patterns][1] == "^ssh://x/(.*)$")
assert(browse.opts.gitbrowse.url_patterns["git%.example"].branch == "/b/{{branch}}")
''')
    subprocess.run(
        ["nvim", "--clean", "--headless", "-l", str(script)],
        env={"HOME": str(home), "PATH": os.environ["PATH"]},
        check=True,
        capture_output=True,
        text=True,
    )


def test_empty_private_remote_fragment_preserves_snacks_defaults(
    tmp_path: Path,
) -> None:
    target, home, env = fixture_target(tmp_path, "ML-DFC6YK6VJQ", work_values=True)
    local = target / "mise.local.toml"
    local.write_text(
        local.read_text().replace(
            "neovim_scm_remote_patterns = '''        { \"^ssh://x/(.*)$\", \"https://example/%1\" },'''",
            'neovim_scm_remote_patterns = ""',
        )
    )
    dotfiles(target, env, "--yes")
    rendered = (home / ".config/nvim/lua/plugins/gitbrowse.work.lua").read_text()
    assert "remote_patterns" not in rendered
    assert "url_patterns" in rendered


@pytest.mark.parametrize(
    "config,message",
    [
        ("", "required on the work host"),
        ('[[index]]\nurl = "not-a-url"\n', "valid HTTP(S) URL"),
        (
            '[[index]]\nurl = "https://one.example"\ndefault = true\n'
            '[[index]]\nurl = "https://two.example"\ndefault = true\n',
            "multiple indexes",
        ),
    ],
)
def test_python_index_facts_reject_invalid_config(config: str, message: str) -> None:
    result = subprocess.run(
        [str(PYTHON_INDEX / "files/python-index-facts")],
        env={**os.environ, "PYTHON_INDEX_CONFIG": config},
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert message in result.stderr


def test_repair_mason_removes_only_broken_python_packages(tmp_path: Path) -> None:
    home = tmp_path / "home"
    mason = home / ".local/share/nvim/mason"
    packages = mason / "packages"
    for name in ("healthy", "broken", "nonexec", "node-native"):
        (packages / name).mkdir(parents=True)
    healthy = packages / "healthy/venv/bin/python"
    healthy.parent.mkdir(parents=True)
    healthy.write_text("#!/bin/sh\n")
    healthy.chmod(0o755)
    broken = packages / "broken/venv/bin/python"
    broken.parent.mkdir(parents=True)
    broken.symlink_to("missing-python")
    nonexec = packages / "nonexec/venv/bin/python"
    nonexec.parent.mkdir(parents=True)
    nonexec.write_text("not executable\n")
    (mason / "bin").mkdir()
    (mason / "bin/broken-tool").symlink_to("../packages/broken/bin/tool")
    (mason / "bin/healthy-tool").symlink_to("../packages/healthy/venv/bin/python")
    (packages / "node-native/python-tool").symlink_to("../healthy/venv/bin/python")
    (mason / "unrelated").symlink_to("nowhere")
    subprocess.run(
        ["python3", str(NVIM / "files/repair-mason.py")],
        env={**os.environ, "HOME": str(home)},
        check=True,
    )
    assert sorted(path.name for path in packages.iterdir()) == [
        "healthy",
        "node-native",
    ]
    assert (mason / "bin/healthy-tool").is_symlink()
    assert (packages / "node-native/python-tool").is_symlink()
    assert not (mason / "bin/broken-tool").exists()
    assert not (mason / "unrelated").exists()


@pytest.mark.parametrize(
    ("host", "lazy", "mason"),
    [
        ("Thurstons-MacBook-Pro", "+Lazy! sync", True),
        ("ML-DFC6YK6VJQ", "+Lazy! restore", False),
    ],
)
def test_setup_task_preserves_command_order_and_propagates_failure(
    tmp_path: Path, host: str, lazy: str, mason: bool
) -> None:
    target, home, env = fixture_target(
        tmp_path, host, work_values=host == "ML-DFC6YK6VJQ"
    )
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake = fake_bin / "nvim"
    fake.write_text(
        '#!/bin/sh\nprintf "%s\\n" "$*" >> "$HOME/calls"\n[ "${FAIL_NVIM:-}" != 1 ]\n'
    )
    fake.chmod(0o755)
    env["PATH"] = f"{fake_bin}:{env['PATH']}"
    subprocess.run(
        ["mise", "-C", str(target), "run", "neovim:setup"], env=env, check=True
    )
    expected = [f"--headless {lazy} +qa"]
    if mason:
        expected.append("--headless +MasonToolsUpdateSync +qa")
    expected.append(
        '--headless +lua local ok, err = xpcall(function() require("nvim-treesitter").update(nil, { summary = true }):wait(600000) end, debug.traceback); if not ok then vim.api.nvim_err_writeln(err); vim.cmd.cquit() end +qa',
    )
    assert (home / "calls").read_text().splitlines() == expected
    (home / "calls").unlink()
    env["FAIL_NVIM"] = "1"
    failed = subprocess.run(
        ["mise", "-C", str(target), "run", "neovim:setup"], env=env, check=False
    )
    assert failed.returncode != 0
    assert (home / "calls").read_text().splitlines() == [f"--headless {lazy} +qa"]
