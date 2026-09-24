from pathlib import Path
import tomllib

TARGET = Path(__file__).resolve().parents[1] / "bootstrap/targets/pod042"


def test_samba_password_is_rendered_privately() -> None:
    config = tomllib.loads((TARGET / "mise.sharing.toml").read_text())["bootstrap"]
    credential = config["files"]["/etc/ansiblonomicon/samba/credentials"]

    assert config["secrets"] == {"samba_media_password": "SAMBA_MEDIA_PASSWORD"}
    assert credential["mode"] == "0600"
    assert 'secret(name="samba_media_password")' in credential["content"]
