# Pod042 bootstrap

Pod042 manages itself after its first successful `mise pod042` converge. This runbook records the manual-once path from an empty TrueNAS VM to that boundary. It is deliberately not an automated rebuild pipeline.

## Fixed inputs

- VM: `pod042`
- Address: `192.168.1.94/24`; gateway and DNS: `192.168.1.1`
- NIC MAC: `02:d3:b5:97:4f:0f`; `.94` was verified silent before bootstrap, with its UniFi reservation deferred
- Boot zvol: `performance/pod042-boot`
- Shared dataset/export: `performance/pod042` at `/mnt/performance/pod042`; the guest mount is added in Phase 3
- Image: Debian generic amd64 build `20260722-2547`
- Image URL: `https://cloud.debian.org/cdimage/cloud/trixie/20260722-2547/debian-13-generic-amd64-20260722-2547.qcow2`
- Image SHA-512: `1ff07be8406c4abcb75662a351b6124408c4a2795801037f8e4fe9ee27084ee2112bef92222f4bbeb9f7df8df1062971a9692f4c82f3da3c01fda6b1493906b9`
- TrueNAS staging directory: `/mnt/performance/home/admin/pod042`

The filesystem dataset and zvol intentionally have different ZFS names. ZFS cannot create both at `performance/pod042`.

## 1. Prepare and verify the image

Run on the workstation:

```sh
set -euo pipefail
bootstrap_dir=$(mktemp -d "${TMPDIR:-/tmp}/pod042-bootstrap.XXXXXX")
image=debian-13-generic-amd64-20260722-2547.qcow2
image_url=https://cloud.debian.org/cdimage/cloud/trixie/20260722-2547/$image
image_sha512=1ff07be8406c4abcb75662a351b6124408c4a2795801037f8e4fe9ee27084ee2112bef92222f4bbeb9f7df8df1062971a9692f4c82f3da3c01fda6b1493906b9

cd "$bootstrap_dir"
curl --fail --location --output "$image" "$image_url"
printf '%s  %s\n' "$image_sha512" "$image" | shasum -a 512 -c -

ssh truenas 'install -d -m 0755 /mnt/performance/home/admin/pod042'
scp "$image" truenas:/mnt/performance/home/admin/pod042/
ssh truenas "cd /mnt/performance/home/admin/pod042 && printf '%s  %s\\n' '$image_sha512' '$image' | sha512sum -c - && qemu-img info --output=json '$image'"
```

The dated artifact and checksum came from Debian's signed-build directory rather than the mutable `latest` path. The accepted OS decision is the `generic` image, not the reduced-driver `genericcloud` variant.

## 2. Build and upload the NoCloud seed

Select the public half of the personal Git SSH key from the 1Password SSH agent. No private key or other secret belongs in the seed.

```sh
onepassword_agent="$HOME/Library/Group Containers/2BUA8C4S2C.com.1password/t/agent.sock"
public_key=$(SSH_AUTH_SOCK="$onepassword_agent" ssh-add -L | grep ' Git SSH Key$')
test -n "$public_key"

seed_dir="$bootstrap_dir/seed"
mkdir -p "$seed_dir"

cat > "$seed_dir/meta-data" <<'EOF'
instance-id: pod042-20260722-2547
local-hostname: pod042
EOF

cat > "$seed_dir/user-data" <<EOF
#cloud-config
hostname: pod042
manage_etc_hosts: true
package_update: true
packages:
  - ca-certificates
  - curl
  - git
users:
  - name: thurstonsand
    uid: 1000
    groups: [sudo]
    sudo: "ALL=(ALL) NOPASSWD:ALL"
    shell: /bin/bash
    lock_passwd: true
    ssh_authorized_keys:
      - $public_key
ssh_pwauth: false
disable_root: true
growpart:
  mode: auto
  devices: [/]
resize_rootfs: true
EOF

cat > "$seed_dir/network-config" <<'EOF'
version: 2
ethernets:
  uplink:
    match:
      macaddress: "02:d3:b5:97:4f:0f"
    dhcp4: false
    dhcp6: false
    addresses: [192.168.1.94/24]
    routes:
      - to: default
        via: 192.168.1.1
    nameservers:
      addresses: [192.168.1.1]
EOF

hdiutil makehybrid -o "$bootstrap_dir/pod042-seed.iso" "$seed_dir" \
  -iso -joliet -default-volume-name cidata
scp "$bootstrap_dir/pod042-seed.iso" truenas:/mnt/performance/home/admin/pod042/
```

The `cidata` volume label and the three root-level files are required by NoCloud. Replacing the ISO does not reapply cloud-init to an initialized disk with the same instance state.

## 3. Create the durable TrueNAS resources

From the repository checkout on the workstation, preview and then apply only pod042's resources:

```sh
set -a
source .env
set +a
mise truenas --check -t pod042
mise truenas -t pod042
```

This creates the shared filesystem dataset and NFS export, the 80 GiB boot zvol, and the stopped VM. The VM has no SPICE display and no declared CDROM device.

Verify before importing anything:

```sh
ssh truenas 'midclt call pool.dataset.query '\''[["id","=","performance/pod042-boot"]]'\'' | jq '\''.[0] | {id,type,volsize}'\'''
ssh truenas 'midclt call vm.query '\''[["name","=","pod042"]]'\'' | jq '\''.[0] | {id,name,autostart,status,devices}'\'''
```

The dataset ID must be exactly `performance/pod042-boot`, its type must be `VOLUME`, and the VM must be stopped. Stop if any fact differs.

## 4. Import the image and attach the temporary seed

Use TrueNAS's image-import API. Do not `dd` a QCOW2 into the zvol; that would put the QCOW2 container where the guest expects a raw disk.

```sh
ssh truenas 'midclt call -j true vm.import_disk_image \
  "{\"diskimg\":\"/mnt/performance/home/admin/pod042/debian-13-generic-amd64-20260722-2547.qcow2\",\"zvol\":\"performance/pod042-boot\"}"'
set -a
source .env
set +a
: "${TRUENAS_BECOME_PASSWORD:?TRUENAS_BECOME_PASSWORD is missing}"
printenv TRUENAS_BECOME_PASSWORD |
  ssh truenas 'sudo -S -p "" qemu-img info --output=json /dev/zvol/performance/pod042-boot'
unset TRUENAS_BECOME_PASSWORD

set -euo pipefail
vm_id=$(ssh truenas "midclt call vm.query '[[\"name\",\"=\",\"pod042\"]]'" | jq -er '.[0].id')
test "$vm_id" -gt 0
ssh truenas "midclt call vm.device.create '{\"dtype\":\"CDROM\",\"vm\":$vm_id,\"order\":1003,\"attributes\":{\"path\":\"/mnt/performance/home/admin/pod042/pod042-seed.iso\"}}'"
ssh truenas "midclt call vm.start $vm_id"
```

The import job may remain near 98% while finishing. Do not cancel it, retry it, or start the VM before the job returns. The temporary CDROM is intentionally unmanaged because `local.truenas.vm` preserves but cannot delete undeclared devices.

## 5. Verify cloud-init and detach the seed

```sh
ssh -A -o StrictHostKeyChecking=accept-new thurstonsand@192.168.1.94
cloud-init status --wait
hostnamectl --static
ip -brief address
findmnt /
exit

set -euo pipefail
vm_id=$(ssh truenas "midclt call vm.query '[[\"name\",\"=\",\"pod042\"]]'" | jq -er '.[0].id')
cdrom_id=$(ssh truenas "midclt call vm.device.query '[[\"vm\",\"=\",$vm_id],[\"dtype\",\"=\",\"CDROM\"]]'" | jq -er '.[0].id')
test "$cdrom_id" -gt 0
ssh truenas "midclt call vm.stop $vm_id"
ssh truenas "midclt call vm.device.delete $cdrom_id '{\"zvol\":false,\"raw_file\":false,\"force\":false}'"
ssh truenas "midclt call vm.start $vm_id"
ssh -A thurstonsand@192.168.1.94 'test "$(hostname -s)" = pod042'
```

If SSH never becomes reachable, leave the seed attached and add a temporary SPICE display for diagnosis. SPICE is a fallback, not part of the desired VM definition.

## 6. Clone and perform the first local converge

The Phase 1 repository slice must be on `main` before cloning. Forward the workstation's 1Password SSH agent for this initial clone; unattended Git credentials are provisioned later.

```sh
set -euo pipefail
onepassword_agent="$HOME/Library/Group Containers/2BUA8C4S2C.com.1password/t/agent.sock"
github_host_key='github.com ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIOMqqnkVzrm0SdG6UOoqKLsabgH5C9okWi0dh2l9GKJl'

SSH_AUTH_SOCK="$onepassword_agent" ssh -A thurstonsand@192.168.1.94 "
  set -eu
  install -d -m 0700 ~/.ssh
  touch ~/.ssh/known_hosts
  chmod 0600 ~/.ssh/known_hosts
  grep -qxF '$github_host_key' ~/.ssh/known_hosts || printf '%s\\n' '$github_host_key' >> ~/.ssh/known_hosts
  mkdir -p ~/code
  git clone git@github.com:thurstonsand/ansiblonomicon.git ~/code/ansiblonomicon
"

set -a
source .env
set +a
: "${OP_SERVICE_ACCOUNT_TOKEN:?OP_SERVICE_ACCOUNT_TOKEN is missing}"
printenv OP_SERVICE_ACCOUNT_TOKEN |
  SSH_AUTH_SOCK="$onepassword_agent" ssh thurstonsand@192.168.1.94 '
    set -eu
    umask 077
    install -d -m 0700 ~/.config/op-service-account
    token_tmp=$(mktemp ~/.config/op-service-account/token.XXXXXX)
    trap '\''rm -f "$token_tmp"'\'' EXIT
    cat > "$token_tmp"
    test -s "$token_tmp"
    install -m 0600 "$token_tmp" ~/.config/op-service-account/token
  '
unset OP_SERVICE_ACCOUNT_TOKEN

SSH_AUTH_SOCK="$onepassword_agent" ssh thurstonsand@192.168.1.94 '
  set -eu
  curl -LsSf https://astral.sh/uv/install.sh -o /tmp/uv-install.sh
  sh /tmp/uv-install.sh
  curl -LsSf https://mise.run -o /tmp/mise-install.sh
  sh /tmp/mise-install.sh
  cd ~/code/ansiblonomicon
  export PATH="$HOME/.local/bin:$PATH"
  mise trust --quiet
  mise pod042
'

ssh thurstonsand@192.168.1.94 'cat > /tmp/merge-pi-oauth.py' <<'PY'
import json
import os
from pathlib import Path
import sys

path = Path.home() / ".pi/agent/auth.json"
incoming = json.load(sys.stdin)
credential = incoming.get("openai-codex")
if not isinstance(credential, dict) or credential.get("type") != "oauth":
    raise SystemExit("incoming openai-codex OAuth credential is invalid")
existing = json.loads(path.read_text())
existing["openai-codex"] = credential
temporary = path.with_suffix(".json.tmp")
temporary.write_text(json.dumps(existing, indent=2) + "\n")
os.chmod(temporary, 0o600)
temporary.replace(path)
PY

python3 - <<'PY' |
import json
from pathlib import Path

credentials = json.loads((Path.home() / ".pi/agent/auth.json").read_text())
credential = credentials.get("openai-codex")
if not isinstance(credential, dict) or credential.get("type") != "oauth":
    raise SystemExit("workstation openai-codex OAuth credential is missing")
print(json.dumps({"openai-codex": credential}))
PY
  ssh thurstonsand@192.168.1.94 'trap '\''rm -f /tmp/merge-pi-oauth.py'\'' EXIT; python3 /tmp/merge-pi-oauth.py'
```

Only the service-account token and the single unmanaged `openai-codex` OAuth credential cross their commands' stdin. `printenv` receives only the variable name as an argument, the remote side rejects an empty token before installation, the OAuth merge is atomic, and the repository-wide `.env` and other Pi credentials are never copied to pod042. Chezmoi preserves the unmanaged OAuth entry on later converges. The GitHub Ed25519 host key is pinned to GitHub's published key rather than accepted through TOFU.

Verify the managed agent boundary and a guest reboot:

```sh
ssh thurstonsand@192.168.1.94 'test -x ~/.npm-global/bin/pi; test -f ~/.pi/agent/settings.json; cd ~/code/ansiblonomicon && ~/.local/bin/mise pod042 --check'
ssh thurstonsand@192.168.1.94 'sudo systemctl reboot' || true
until ssh -o ConnectTimeout=5 thurstonsand@192.168.1.94 'test "$(hostname -s)" = pod042'; do sleep 5; done
```

Start the continuation Pi session from `~/code/ansiblonomicon`. Phase 1 is complete only after that session receives the handoff and acknowledges the remaining implementation phases.

## Execution record

Fill this during the build rather than reconstructing it later.

- Image downloaded and workstation checksum verified: 2026-07-25, SHA-512 matched
- NAS checksum and source `qemu-img info` verified: 2026-07-25, QCOW2 clean, 3 GiB virtual size
- UniFi `.94` reservation for `02:D3:B5:97:4F:0F`: deferred; Thurston directed the bootstrap to proceed after `.94` was verified silent and absent from existing static leases
- TrueNAS scoped check/apply: 2026-07-25, second apply changed zero tasks
- Image-import job completed: 2026-07-25; repeated cleanly after `.91` was found reserved to an Apple device and pod042 moved to `.94`
- Temporary CDROM device ID: `56`
- `cloud-init status --wait`: done with no errors on `.94`; hostname, static route, `1000:1000` identity, and 78.5 GiB root filesystem verified
- Seed detached and SSH restored: passed; VM devices contain only the boot zvol and expected NIC
- First local `mise pod042` converge: passed after correcting pod042's Chezmoi config to use service-account mode; second converge changed zero tasks
- Pi OAuth bootstrap: copied only the workstation's unmanaged `openai-codex` credential through SSH stdin; Pi 0.82.0 replied `pod042-ready`
- Guest reboot returned unattended: passed; post-reboot `mise pod042 --check` changed zero tasks
- On-VM Pi handoff session: `019f9762-b802-7e44-9291-665af00d0421` acknowledged hostname, checkout, clean `178d0fd` HEAD, and the Phase 2 mission
- Phase 2 development baseline: Node 24, audited shell/tool roles, Docker client-only packages, shpool, sessions, terminal theme, tmux plugins, and pod042 guidance in the existing project-local software-provisioning skill converged; repeat converge changed zero tasks
- Workstation integration: the macOS terminal-theme detector mirrors to pod042; `gty ssh pod042` exposes the GhosttyKit clipboard bridge, and Pi loads the managed `@thurstonsand/pi-paste` package for `alt+v` and `/paste`
- Phase 3 service-account boundary: `op user get --me`, agent-vault read, temporary item create/delete, and denial of the unavailable `Private` vault passed; `.env` regenerated non-interactively at mode `0600`
- Phase 3 Git identity: agent-vault item `Git SSH Key` deployed; unattended GitHub authentication, repository read, and SSH commit signing passed
- Phase 3 TrueNAS identity: dedicated agent-vault item `pod042 TrueNAS SSH Key` (`yqt5h3i7ppiv56ejqaxlvxunuq`), fingerprint `SHA256:QAGBCAoELQIWnTwZluGrYXgRZsOQGH9EW3mVBla45QQ`, authorized only as an additional `admin` key; pinned TrueNAS host-key fingerprint `SHA256:Y/v95l/67PcMqsZm/LmXLWIL5o9YaixqkYmKXKNynZ8`
- Phase 3 storage and Docker boundary: NFSv4 mounted from `192.168.1.68:/mnt/performance/pod042` at the symmetric path with `1000:1000` user and `0:0` root identity preserved; remote Docker 27.1.1 container and bind-mount smoke tests passed; no local Docker daemon packages or units were introduced
- Phase 3 idempotence: two scoped TrueNAS applies and two full local pod042 converges each changed zero tasks
