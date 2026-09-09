from pathlib import Path
import subprocess
import tomllib

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "bootstrap/targets/pod042"


def test_sharing_declares_one_media_share() -> None:
    config = tomllib.loads((TARGET / "mise.sharing.toml").read_text())["bootstrap"]
    smb = (TARGET / "sharing/smb.conf").read_text()

    assert set(config["packages"]) == {"apt:samba", "apt:smbclient"}
    assert "[media]" in smb
    assert "path = /mnt/ark/media" in smb
    assert "valid users = thurstonsand" in smb
    assert "force group = media" in smb
    assert "/mnt/black-box" not in smb
    assert config["services"]["smbd"]["enabled"] is True
    assert config["services"]["nmbd"] == {"state": "stopped", "enabled": False}
    assert config["services"]["winbind"] == {
        "state": "stopped",
        "enabled": False,
    }
    assert config["services"]["samba-ad-dc"] == {
        "state": "stopped",
        "enabled": False,
    }


def test_sharing_is_smb3_only_and_not_discoverable_over_netbios() -> None:
    smb = (TARGET / "sharing/smb.conf").read_text()

    assert "server min protocol = SMB3" in smb
    assert "disable netbios = yes" in smb
    assert "smb ports = 445" in smb
    assert "interfaces = lo enp5s0" in smb
    assert "map to guest = never" in smb


def test_samba_password_is_rendered_privately_and_reconciled() -> None:
    config = tomllib.loads((TARGET / "mise.sharing.toml").read_text())["bootstrap"]
    credential = config["files"]["/etc/ansiblonomicon/samba/credentials"]
    reconciler = config["files"]["/usr/local/sbin/reconcile-samba-account"]

    assert config["secrets"] == {"samba_media_password": "SAMBA_MEDIA_PASSWORD"}
    assert credential["template"] is True
    assert credential["mode"] == "0600"
    assert 'secret(name="samba_media_password")' in credential["content"]
    assert reconciler["source"] == "sharing/reconcile-account.sh"
    assert reconciler["mode"] == "0755"
    subprocess.run(
        ["sh", "-n", str(TARGET / reconciler["source"])],
        check=True,
    )


def test_lunar_tear_does_not_receive_smb_access() -> None:
    policy = (ROOT / "terraform/unifi/policies.tf").read_text()

    assert 'port               = "80,443,32400"' in policy
