#!/usr/bin/env bash
#
# premove-backup.sh — one-shot restic backup of the black-box subset from the
# LIVE TrueNAS host, before the physical move (bunker rebuild, ticket 04).
#
# Runs from a workstation. Credentials are read from 1Password at runtime and
# handed to the NAS over ssh stdin; nothing is written to disk and nothing
# appears in a command line or process list.
#
# Required 1Password item — vault "agent", item "Backblaze", fields:
#   bucket               B2 bucket name (e.g. thurstons-bunker)
#   key id               B2 application key ID     (restic B2_ACCOUNT_ID)
#   applicationKey       B2 application key        (restic B2_ACCOUNT_KEY)
#   repository password  restic repository encryption password — generate a long
#                        random string; LOSING IT LOSES THE BACKUP
#
# What it does, on the NAS docker daemon via the official restic image:
#   1. takes a ZFS snapshot of each source dataset (consistent sqlite reads)
#   2. bind-mounts each snapshot READ-ONLY at its POST-move path, so snapshot
#      paths in the repo already match the rebuilt host's layout
#   3. restic init (only if the repo is absent), backup, check
#   4. restores a sample path to /tmp on the NAS and diffs it against the source
#   5. destroys the ZFS snapshots it created
#
# Safe to re-run: every run takes fresh snapshots under a fresh timestamp and
# adds a deduplicated restic snapshot to the same repository.
#
# Usage: docs/wayfinding/bunker-rebuild/scripts/premove-backup.sh
set -euo pipefail

readonly OP_ITEM="op://agent/Backblaze"
readonly NAS_HOST="${NAS_HOST:-truenas}"
readonly RESTIC_IMAGE="${RESTIC_IMAGE:-restic/restic:0.19.1}"
readonly REPO_PATH="${REPO_PATH:-black-box}"

die() {
  printf 'premove-backup: %s\n' "$*" >&2
  exit 1
}

for tool in op ssh mktemp; do
  command -v "$tool" >/dev/null || die "missing required command: $tool"
done

read_secret() {
  local field="$1"
  local value
  value="$(op read --no-newline "${OP_ITEM}/${field}")" ||
    die "could not read ${OP_ITEM}/${field} from 1Password"
  [[ -n "$value" ]] || die "${OP_ITEM}/${field} is empty"
  printf '%s' "$value"
}

repo_password="$(read_secret 'repository password')"
b2_key_id="$(read_secret 'key id')"
b2_application_key="$(read_secret 'applicationKey')"
b2_bucket="$(read_secret 'bucket')"

local_script="$(mktemp)"
trap 'rm -f "$local_script"' EXIT

cat >"$local_script" <<'REMOTE_SCRIPT'
#!/usr/bin/env bash
# Executed on the NAS by premove-backup.sh. Reads four secrets from stdin.
set -euo pipefail

readonly image="$1"
readonly repo_path="$2"
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
readonly stamp
readonly snap="restic-premove-${stamp}"
readonly tag="premove-${stamp}"
readonly verify_dir="/tmp/restic-premove-verify-${stamp}"
readonly cache_dir="/tmp/restic-premove-cache"
readonly sample_path="/mnt/black-box/docker/stacks"

log() { printf '[premove-backup] %s\n' "$*"; }
die() {
  printf '[premove-backup] ERROR: %s\n' "$*" >&2
  exit 1
}

snapshotted_datasets=()
cleanup() {
  local dataset
  for dataset in ${snapshotted_datasets[@]+"${snapshotted_datasets[@]}"}; do
    log "destroying ${dataset}@${snap}"
    midclt call zfs.snapshot.delete "${dataset}@${snap}" >/dev/null ||
      printf '[premove-backup] WARNING: could not destroy %s@%s\n' "$dataset" "$snap" >&2
  done
}
trap cleanup EXIT

command -v docker >/dev/null || die "docker not found on the NAS"
command -v midclt >/dev/null || die "midclt not found on the NAS"

IFS= read -r RESTIC_PASSWORD || die "missing repository password on stdin"
IFS= read -r B2_ACCOUNT_ID || die "missing B2 key id on stdin"
IFS= read -r B2_ACCOUNT_KEY || die "missing B2 application key on stdin"
IFS= read -r b2_bucket || die "missing B2 bucket on stdin"
export RESTIC_PASSWORD B2_ACCOUNT_ID B2_ACCOUNT_KEY
export RESTIC_REPOSITORY="b2:${b2_bucket}:${repo_path}"
export RESTIC_CACHE_DIR=/cache

mkdir -p "$cache_dir" "$verify_dir"

# Snapshot a dataset and echo the path its snapshot is exposed at.
snapshot_dir() {
  local dataset="$1" mountpoint="$2" path
  # admin lacks direct `zfs snapshot` rights; the middleware grants them
  midclt call zfs.snapshot.create "{\"dataset\": \"${dataset}\", \"name\": \"${snap}\"}" >/dev/null ||
    die "could not snapshot ${dataset}"
  snapshotted_datasets+=("$dataset")
  path="${mountpoint}/.zfs/snapshot/${snap}"
  ls "$path" >/dev/null || die "snapshot directory did not appear at ${path}"
  printf '%s' "$path"
}

mounts=()
add_source() {
  mounts+=(--mount "type=bind,source=$1,destination=$2,readonly")
}

log "snapshotting source datasets as @${snap}"
docker_dir="$(snapshot_dir performance/docker /mnt/performance/docker)"
plex_dir="$(snapshot_dir performance/apps/plex /mnt/performance/apps/plex)"
watch_dir="$(snapshot_dir capacity/watch /mnt/capacity/watch)"

# Mounted at the post-move layout (ticket 10) so this repo keeps working after
# the rebuild: anypod's db is application data on black-box, its transcripts
# ride along with the media on ark. Plex is the one divergence — post-move it
# folds into black-box/docker, but it cannot be nested inside another
# read-only bind mount here, so it gets its own top-level path.
add_source "$docker_dir" /mnt/black-box/docker
add_source "$plex_dir" /mnt/black-box/plex
add_source "${watch_dir}/anypod/data/db" /mnt/black-box/anypod/db
add_source "${watch_dir}/anypod/data/transcripts" /mnt/ark/anypod/transcripts

targets=(
  /mnt/black-box/docker
  /mnt/black-box/plex
  /mnt/black-box/anypod/db
  /mnt/ark/anypod/transcripts
)

if [[ -d /mnt/performance/pod042 ]] && [[ -n "$(ls -A /mnt/performance/pod042)" ]]; then
  pod042_dir="$(snapshot_dir performance/pod042 /mnt/performance/pod042)"
  add_source "$pod042_dir" /mnt/black-box/agents
  targets+=(/mnt/black-box/agents)
else
  log "performance/pod042 is empty; nothing to back up from it"
fi

restic_run() {
  docker run --rm \
    --env RESTIC_REPOSITORY --env RESTIC_PASSWORD \
    --env B2_ACCOUNT_ID --env B2_ACCOUNT_KEY --env RESTIC_CACHE_DIR \
    --mount "type=bind,source=${cache_dir},destination=/cache" \
    "$@"
}

restic_backup() {
  restic_run "${mounts[@]}" "$image" "$@"
}

if restic_backup cat config >/dev/null 2>&1; then
  log "repository ${RESTIC_REPOSITORY} already exists"
else
  log "initializing repository ${RESTIC_REPOSITORY}"
  restic_backup init
fi

log "backing up: ${targets[*]}"
restic_backup backup \
  --host bunker \
  --tag premove \
  --tag "$tag" \
  --exclude "/mnt/black-box/plex/config/Library/Application Support/Plex Media Server/Cache" \
  --exclude "/mnt/black-box/plex/config/Library/Application Support/Plex Media Server/Media" \
  --exclude "/mnt/black-box/plex/config/Library/Application Support/Plex Media Server/Crash Reports" \
  --exclude "/mnt/black-box/plex/logs" \
  "${targets[@]}"

log "checking repository structure"
restic_backup check

log "restoring ${sample_path} to ${verify_dir} for verification"
restic_run \
  --mount "type=bind,source=${verify_dir},destination=/verify" \
  "$image" restore "latest:${sample_path}" --tag "$tag" --host bunker --target /verify

diff -r "${verify_dir}" "${docker_dir}/stacks" ||
  die "restored sample does not match the source snapshot"
log "verified restore matches source: ${verify_dir}"

log "snapshots now in the repository:"
restic_backup snapshots --compact
log "done. Restored sample left at ${verify_dir} on the NAS (tmpfs, clears on reboot)."
REMOTE_SCRIPT

remote_script="/tmp/premove-backup-remote.$$.sh"
# The remote paths and image tag are deliberately expanded client side.
# shellcheck disable=SC2029
ssh "$NAS_HOST" "cat > ${remote_script} && chmod 700 ${remote_script}" <"$local_script"

# shellcheck disable=SC2029
printf '%s\n' "$repo_password" "$b2_key_id" "$b2_application_key" "$b2_bucket" |
  ssh "$NAS_HOST" \
    "bash ${remote_script} '${RESTIC_IMAGE}' '${REPO_PATH}'; rc=\$?; rm -f ${remote_script}; exit \$rc"
