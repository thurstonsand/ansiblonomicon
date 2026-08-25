#!/usr/bin/env bash
# Predicate check for the direnv+poe+pre-commit -> mise+hk migration.
# Re-runnable. Exits with the number of failed assertions.
#
# NOT non-destructive: assertion 2 deletes and rebuilds .venv, because proving
# which interpreter a fresh venv lands on is the whole point. The
# rebuild is from uv.lock, so it reconciles rather than loses. It leaves .env
# alone, which is the file that would actually hurt.
#
# Two contaminants this works around, both from any shell started before .envrc
# was deleted: UV_PYTHON_PREFERENCE=only-managed, which makes uv rebuild .venv on
# every call, and the direnv-exported secrets, which make a child shell look
# correctly configured when it merely inherited everything. Every assertion that
# could be fooled by inheritance runs through clean().
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

fails=0
ok()    { printf '  \033[32mPASS\033[0m  %s\n' "$1"; }
bad()   { printf '  \033[31mFAIL\033[0m  %s\n' "$1"; fails=$((fails + 1)); }
head_() { printf '\n\033[1m%s\033[0m\n' "$1"; }

# Resolve the tools before scrubbing the environment: Homebrew's prefix is a
# laptop fact, and pod042 and the agent sandboxes keep mise and uv in ~/.local/bin.
# Skip mise's shim directory. mise generates shims for tools it does not manage,
# including uv, and a shim resolves through mise rather than being the binary. In
# a PATH this narrow it has nothing to fall through to and dies with "No version
# is set for shim", which looks exactly like a broken venv.
real_bin() {
  local p
  for p in $(type -aP "$1"); do
    case "$p" in */mise/shims/*) continue ;; esac
    printf '%s\n' "$p"; return 0
  done
  return 1
}
mise_bin=$(real_bin mise) || { echo "mise not on PATH"; exit 127; }
uv_bin=$(real_bin uv)     || { echo "uv not on PATH";   exit 127; }
clean_path="$(dirname "$mise_bin"):$(dirname "$uv_bin"):/usr/bin:/bin"
clean() { env -i HOME="$HOME" PATH="$clean_path" TERM=dumb "$@"; }

head_ "1. no executable path in this repo still invokes direnv"
[ ! -e .envrc ] && ok ".envrc deleted from the working tree" || bad ".envrc still present"
# Only entrypoints that RUN direnv count. direnv stays a host tool, so the
# Brewfiles and ansible host configs legitimately keep installing it, and
# chezmoi/ still wires the shell hook and the tmux clean-env wrapper. docs/designs
# is excluded as historical record; the rest of docs/ is NOT — a runbook that
# shells out to `direnv allow` is executable, and one did.
runners=$(grep -rIl -E 'direnv (allow|exec|hook)|direnv@' \
            --exclude-dir=.git --exclude-dir=node_modules --exclude-dir=.venv \
            --exclude-dir=chezmoi --exclude-dir=ansible --exclude-dir=designs \
            --exclude="$(basename "$0")" . 2>/dev/null | tr '\n' ' ')
[ -z "$runners" ] && ok "nothing in the repo runs direnv" \
                  || bad "still invoke direnv: $runners"

head_ "2. venv is built on the interpreter mise resolves, byte for byte"
rm -rf .venv
if ! clean mise run bootstrap:deps >/tmp/p1-deps.log 2>&1; then
  bad "bootstrap:deps failed — see /tmp/p1-deps.log"
fi
# Compared by realpath, not by string: `mise which python` walks PATH and lands
# on the 3.14 alias symlink, while tools.python.path names the concrete 3.14.6.
# Same inode, different spelling. Substring matching is not an option either —
# a wrong MISE_DATA_DIR still contains "/mise/installs/python/".
want=$(clean mise which python); want=$(realpath "$want")
home=$(grep '^home' .venv/pyvenv.cfg | cut -d' ' -f3)
[ "$(realpath "$home/python")" = "$want" ] && ok "venv interpreter is mise's ($want)" \
                                            || bad "venv on $home/python, mise resolves $want"
n=$(ls .venv/bin | wc -l | tr -d ' ')
[ "$n" -gt 40 ] && ok "venv populated ($n entries in bin/)" || bad "venv looks empty ($n entries)"

head_ "3. the venv actually works"
v=$(.venv/bin/ansible --version 2>/dev/null | sed -n 1p)
[ -n "$v" ] && ok "$v" || bad "ansible failed to run from .venv"

head_ "4. environment contract, resolved in a shell that inherited nothing"
envout=$(clean mise env -s bash 2>/dev/null)
get() { printf '%s\n' "$envout" | sed -n "s/^export $1=//p" | tr -d "'\""; }
[ -n "$(get ANSIBLE_CONFIG)" ] && ok "ANSIBLE_CONFIG=$(get ANSIBLE_CONFIG)" || bad "ANSIBLE_CONFIG unset"
[ -n "$(get SUDO_ASKPASS)" ]   && ok "SUDO_ASKPASS set"                     || bad "SUDO_ASKPASS unset"
[ "$(realpath "$(get UV_PYTHON)" 2>/dev/null)" = "$want" ] && ok "UV_PYTHON resolves to mise's interpreter" \
                                                           || bad "UV_PYTHON=$(get UV_PYTHON), mise resolves $want"
[ -x "$(get UV_PYTHON)" ]      && ok "UV_PYTHON is executable"              || bad "UV_PYTHON names a nonexistent path"
[ -z "$(get UV_PYTHON_PREFERENCE)" ] && ok "UV_PYTHON_PREFERENCE not exported" \
                                     || bad "UV_PYTHON_PREFERENCE still set"
[ -z "$(get DIRENV_DIR)" ] && ok "no direnv variables in the resolved env" || bad "direnv still active"
case ":$(get PATH):" in
  *":$PWD/.venv/bin:"*) ok "venv/bin is on PATH (activation works)" ;;
  *)                    bad "venv/bin missing from PATH" ;;
esac
printf '%s\n' "$envout" | grep -q '^export CLOUDFLARE_ACCOUNT_ID=' \
  && ok "$(printf '%s\n' "$envout" | grep -c '^export ') vars exported, .env secrets included" \
  || bad ".env secrets did not load"

head_ "5. bootstrap succeeds and is a cache no-op on the second run"
# Both statuses are checked: a bootstrap that fails fast would otherwise satisfy
# the duration assertion below and report green.
clean mise run bootstrap >/tmp/p1-boot1.log 2>&1 || bad "first bootstrap failed — /tmp/p1-boot1.log"
t0=$EPOCHREALTIME
clean mise run bootstrap --verbose >/tmp/p1-boot2.log 2>&1 || bad "second bootstrap failed — /tmp/p1-boot2.log"
t1=$EPOCHREALTIME
ms=$(awk "BEGIN{printf \"%d\", ($t1-$t0)*1000}")
# Timing alone proves nothing: a warm `uv sync` returns in ~40ms and would sail
# under any threshold. Assert the command did not run at all.
if grep -qE 'uv sync|npm install' /tmp/p1-boot2.log; then
  bad "second bootstrap re-ran real work — cache is not holding"
else
  ok "second bootstrap ran no uv/npm work (${ms}ms)"
fi

head_ "6. a shell that generates .env sees the secrets it generated"
# The repo's own path calls 1Password and needs Touch ID, so the ORDERING is
# proven against a scratch project with the same shape: _.file naming a file the
# enter hook creates. This is what would break if mise reordered hook execution
# against env resolution. The repo-side assertion is only that the guard exists.
scratch=$(mktemp -d)
cat > "$scratch/mise.toml" <<'TOML'
[env]
_.file = ".env"
[hooks]
enter = "mise run gen"
[tasks.gen]
run = "printf 'ORDERING_PROOF=visible\\n' > .env"
TOML
( cd "$scratch" && git init -q . && mise trust --quiet . >/dev/null 2>&1 )
# KNOWN LIMITATION, not a regression to chase: mise resolves _.file before the
# enter hook's write lands, so the shell that generates .env does not see it
# until its next prompt. direnv did not have this problem, because .envrc
# generated and sourced in one evaluation. Asserted as-is so a future mise
# release that fixes it trips this check instead of passing silently.
first=$(cd "$scratch" && clean zsh -l -i <<< 'echo "R:[$ORDERING_PROOF]"; exit' 2>/dev/null | grep -o 'R:\[.*\]')
second=$(cd "$scratch" && clean zsh -l -i <<< 'echo "R:[$ORDERING_PROOF]"; exit' 2>/dev/null | grep -o 'R:\[.*\]')
[ "$first" = 'R:[]' ] && ok "known: generating shell sees no secrets on its first prompt" \
                      || ok "mise now resolves _.file after the enter hook — update the docs"
[ "$second" = 'R:[visible]' ] && ok "the next shell does see them" \
                              || bad "secrets never become visible — _.file is broken"
rm -rf "$scratch"
grep -q 'if \[ ! -f .env \]' mise.toml && ok "bootstrap:secrets regenerates a missing .env" \
                                       || bad "no guard for a missing .env"
[ -f .env ] && ok ".env present and untouched by this script" || bad ".env is missing"

head_ "7. the commit hook"
# git 2.54 config hooks: the hook lives in .git/config, not .git/hooks. There is
# nothing to pin, because a global core.hooksPath cannot shadow it.
[ -n "$(git config --local --get hook.hk-pre-commit.command || true)" ] \
  && ok "hk registered as a git config hook" || bad "no commit hook — commits run unchecked"
[ "$(git config --local --get hook.hk-pre-commit.event || true)" = "pre-commit" ] \
  && ok "bound to the pre-commit event" || bad "hook not bound to pre-commit"
git --version | awk '{split($3,v,"."); exit !(v[1]>2 || (v[1]==2 && v[2]>=54))}' \
  && ok "git $(git --version | awk '{print $3}') supports config hooks" \
  || bad "git is older than 2.54 — the config hook silently will not run"
clean mise run check --help >/dev/null 2>&1 && ok "mise run check exists" || bad "no check task"
uv run poe --help >/dev/null 2>&1 && bad "poe still resolves — Phase 3 was supposed to delete it" \
                                  || ok "poe is gone"
grep -q 'poethepoet' pyproject.toml && bad "poethepoet still a dev dependency" || ok "poethepoet dropped"

head_ "8. shell startup"
for i in 1 2 3; do /usr/bin/time zsh -l -i <<< exit >/dev/null; done 2>&1 | grep real | sed 's/^/  /'

printf '\n'
[ "$fails" -eq 0 ] && printf '\033[32mall assertions passed\033[0m\n' \
                   || printf '\033[31m%d assertion(s) failed\033[0m\n' "$fails"
exit "$fails"
