# Pod042 bootstrap

Pod042 manages itself after its first successful `poe pod042` converge. This runbook records the manual-once path from an empty TrueNAS VM to that boundary. It is deliberately not an automated rebuild pipeline.

## Fixed inputs

- VM: `pod042`
- Address: `192.168.1.91/24`; gateway and DNS: `192.168.1.1`
- NIC MAC: `02:d3:b5:97:4f:0f`
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
    addresses: [192.168.1.91/24]
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
uv run poe truenas --check --tags pod042
uv run poe truenas --tags pod042
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
ssh truenas 'qemu-img info --output=json /dev/zvol/performance/pod042-boot'

set -euo pipefail
vm_id=$(ssh truenas "midclt call vm.query '[[\"name\",\"=\",\"pod042\"]]'" | jq -er '.[0].id')
test "$vm_id" -gt 0
ssh truenas "midclt call vm.device.create '{\"dtype\":\"CDROM\",\"vm\":$vm_id,\"order\":1003,\"attributes\":{\"path\":\"/mnt/performance/home/admin/pod042/pod042-seed.iso\"}}'"
ssh truenas "midclt call vm.start $vm_id"
```

The import job may remain near 98% while finishing. Do not cancel it, retry it, or start the VM before the job returns. The temporary CDROM is intentionally unmanaged because `local.truenas.vm` preserves but cannot delete undeclared devices.

## 5. Verify cloud-init and detach the seed

```sh
ssh -A -o StrictHostKeyChecking=accept-new thurstonsand@192.168.1.91
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
ssh -A thurstonsand@192.168.1.91 'test "$(hostname -s)" = pod042'
```

If SSH never becomes reachable, leave the seed attached and add a temporary SPICE display for diagnosis. SPICE is a fallback, not part of the desired VM definition.

## 6. Clone and perform the first local converge

The Phase 1 repository slice must be on `main` before cloning. Forward the workstation's 1Password SSH agent for this initial clone; unattended Git credentials are provisioned later.

```sh
set -euo pipefail
onepassword_agent="$HOME/Library/Group Containers/2BUA8C4S2C.com.1password/t/agent.sock"
github_host_key='github.com ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIOMqqnkVzrm0SdG6UOoqKLsabgH5C9okWi0dh2l9GKJl'

SSH_AUTH_SOCK="$onepassword_agent" ssh -A thurstonsand@192.168.1.91 "
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
  SSH_AUTH_SOCK="$onepassword_agent" ssh thurstonsand@192.168.1.91 '
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

SSH_AUTH_SOCK="$onepassword_agent" ssh thurstonsand@192.168.1.91 '
  set -eu
  curl -LsSf https://astral.sh/uv/install.sh -o /tmp/uv-install.sh
  sh /tmp/uv-install.sh
  cd ~/code/ansiblonomicon
  ~/.local/bin/uv run poe pod042
'
```

Only the service-account token crosses the second command's stdin. `printenv` receives only the variable name as an argument, the remote side rejects an empty temporary file before installation, and the repository-wide `.env` is never copied to pod042. The GitHub Ed25519 host key is pinned to GitHub's published key rather than accepted through TOFU.

Verify the managed agent boundary and a guest reboot:

```sh
ssh thurstonsand@192.168.1.91 'test -x ~/.npm-global/bin/pi; test -f ~/.pi/agent/settings.json; cd ~/code/ansiblonomicon && ~/.local/bin/uv run poe pod042 --check'
ssh thurstonsand@192.168.1.91 'sudo systemctl reboot' || true
until ssh -o ConnectTimeout=5 thurstonsand@192.168.1.91 'test "$(hostname -s)" = pod042'; do sleep 5; done
```

Start the continuation Pi session from `~/code/ansiblonomicon`. Phase 1 is complete only after that session receives the handoff and acknowledges the remaining implementation phases.

## Execution record

Fill this during the build rather than reconstructing it later.

- Image downloaded and workstation checksum verified: pending
- NAS checksum and `qemu-img info` verified: pending
- TrueNAS scoped check/apply: pending
- Image-import job completed: pending
- Temporary CDROM device ID: pending
- `cloud-init status --wait`: pending
- Seed detached and SSH restored: pending
- First local `poe pod042` converge: pending
- Guest reboot returned unattended: pending
- On-VM Pi handoff session: pending
