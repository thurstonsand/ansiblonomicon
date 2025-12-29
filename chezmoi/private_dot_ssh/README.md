# SSH Configuration Notes

## UDM Pro SSH Key Setup

The UDM Pro (firmware 5.x) wipes `/root/.ssh/authorized_keys` on reboot/upgrade.
A systemd service restores the key from persistent storage.

### If SSH key auth stops working after reboot/upgrade:

```bash
# SSH in with password first
ssh root@192.168.1.1

# Check if the service exists
systemctl status ssh-keys-restore.service

# If service is missing, recreate it:
mkdir -p /data/ssh
cat > /data/ssh/authorized_keys << 'EOF'
# Paste your public key here (from ~/.ssh/*.pub or 1Password)
EOF

cat > /etc/systemd/system/ssh-keys-restore.service << 'EOF'
[Unit]
Description=Restore SSH authorized_keys
After=network.target

[Service]
Type=oneshot
ExecStart=/bin/bash -c 'cat /data/ssh/authorized_keys >> /root/.ssh/authorized_keys'
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now ssh-keys-restore.service

# Verify
cat /root/.ssh/authorized_keys
```

### Get your public key from 1Password:

```bash
# List available SSH keys
op item list --categories "SSH Key"

# Get the public key
op item get "SSH Key Name" --fields "public key"
```
