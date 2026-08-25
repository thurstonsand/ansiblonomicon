#!/usr/bin/env bash
# Rebuild the workstream-E gauntlet rig, scoped to the alerting + zfs_maintenance segment.
set -euo pipefail
VM=pod042test
step() { echo "=== $(date +%T) $*"; }

step "host identity, user, contrib, headers"
limactl shell $VM sudo bash -s <<'EOF'
set -euxo pipefail
hostnamectl set-hostname pod042
grep -q ' pod042$' /etc/hosts || echo "127.0.1.1 pod042" >> /etc/hosts
sed -i 's/^Components: main$/Components: main contrib non-free-firmware/' /etc/apt/sources.list.d/debian.sources
id thurston >/dev/null 2>&1 || useradd -m -s /bin/bash thurston
echo 'thurston ALL=(ALL) NOPASSWD:ALL' > /etc/sudoers.d/thurston; chmod 440 /etc/sudoers.d/thurston
export DEBIAN_FRONTEND=noninteractive
apt-get -qq update
apt-get -qq install -y linux-image-cloud-arm64 linux-headers-cloud-arm64 build-essential dkms rsync curl >/dev/null
EOF

step "reboot onto the kernel we have headers for"
limactl stop pod042test
limactl start pod042test --tty=false
limactl shell $VM sudo bash -c 'uname -r; dpkg -l | grep -c linux-headers'

step "zfs-dkms build (slow)"
limactl shell $VM sudo bash -c 'export DEBIAN_FRONTEND=noninteractive; apt-get install -y zfs-dkms zfsutils-linux > /var/log/zfsinstall.log 2>&1; dkms status'
limactl shell $VM sudo bash -c 'modprobe zfs && zfs version'

step "file-backed ark / black-box pools"
limactl shell $VM sudo bash -s <<'EOF'
set -euxo pipefail
mkdir -p /var/lib/testpools
for p in ark black-box; do for d in a b; do
  [ -f /var/lib/testpools/$p-$d.img ] || truncate -s 4G /var/lib/testpools/$p-$d.img
done; done
zpool list ark >/dev/null 2>&1 || zpool create -o ashift=12 ark mirror /var/lib/testpools/ark-a.img /var/lib/testpools/ark-b.img
zpool list black-box >/dev/null 2>&1 || zpool create -o ashift=12 black-box mirror /var/lib/testpools/black-box-a.img /var/lib/testpools/black-box-b.img
for ds in ark/media black-box/docker black-box/agents; do zfs list "$ds" >/dev/null 2>&1 || zfs create "$ds"; done
mkdir -p /mnt/ark /mnt/black-box
zfs set mountpoint=/mnt/ark ark
zfs set mountpoint=/mnt/black-box black-box
zpool status -x
EOF

step "mock healthchecks + hark on 8099"
limactl shell $VM sudo bash -c 'cat > /usr/local/sbin/mockapi.py; chmod 755 /usr/local/sbin/mockapi.py' < /tmp/rig/mockapi.py
limactl shell $VM sudo bash -s <<'EOF'
set -euxo pipefail
cat > /etc/systemd/system/mockapi.service <<'UNIT'
[Unit]
Description=Offline healthchecks.io + Hark stand-in
[Service]
ExecStart=/usr/bin/python3 /usr/local/sbin/mockapi.py
Restart=no
[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload; systemctl enable --now mockapi.service; sleep 1
curl -s -X POST -H 'Content-Type: application/json' -d '{"slug":"demo","name":"demo"}' http://127.0.0.1:8099/api/v3/checks/ -w ' [%{http_code}]\n'
curl -s -X POST -H 'Content-Type: application/json' -d '{"slug":"demo","name":"demo"}' http://127.0.0.1:8099/api/v3/checks/ -w ' [%{http_code}]\n'
rm -f /var/lib/mockapi-checks.json /var/log/mockapi.jsonl; systemctl restart mockapi
EOF

step "repo sync + uv for thurston"
limactl shell $VM sudo bash -s <<'EOF'
set -euxo pipefail
install -d -o thurston -g thurston /home/thurston/Develop
cat > /usr/local/sbin/sync-repo.sh <<'S'
#!/usr/bin/env bash
set -euo pipefail
rsync -a --delete --exclude .venv --exclude node_modules --exclude .ansible \
  --exclude .mypy_cache --exclude .ruff_cache --exclude .pytest_cache \
  --exclude target --exclude .DS_Store --exclude .git \
  /Users/thurstonsand/Develop/ansiblonomicon/ /home/thurston/Develop/ansiblonomicon/
chown -R thurston:thurston /home/thurston/Develop/ansiblonomicon
S
chmod 755 /usr/local/sbin/sync-repo.sh
/usr/local/sbin/sync-repo.sh
EOF
limactl shell $VM sudo -u thurston -i bash -lc 'curl -LsSf https://astral.sh/uv/install.sh | sh >/dev/null 2>&1; ~/.local/bin/uv --version'
limactl shell $VM sudo -u thurston -i bash -lc 'export PATH=$HOME/.local/bin:$PATH; cd ~/Develop/ansiblonomicon && uv sync 2>&1 | tail -3'
step "rig ready"
