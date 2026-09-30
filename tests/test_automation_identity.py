from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import patch

import pytest

with patch.object(sys, "path", [str(Path(__file__).resolve().parents[1]), *sys.path]):
    from scripts import automation_identity as identity


def test_file_revision_ignores_reads_but_detects_metadata_changes(
    tmp_path: Path,
) -> None:
    path = tmp_path / "identity"
    path.touch()
    metadata = SimpleNamespace(
        st_dev=1,
        st_ino=2,
        st_size=3,
        st_mtime_ns=4,
        st_ctime_ns=5,
        st_mode=0o100600,
        st_uid=6,
        st_gid=7,
        st_atime_ns=8,
    )
    with patch.object(Path, "lstat", return_value=metadata):
        revision = identity.file_revision(path)
        metadata.st_atime_ns = 9
        assert identity.file_revision(path) == revision
        metadata.st_ctime_ns = 10
        assert identity.file_revision(path) != revision


@pytest.mark.parametrize("token", ["", "a b", "a\nb", "a\rb", "a\tb"])
def test_malformed_token_is_rejected(token: str) -> None:
    with pytest.raises(identity.IdentityError):
        identity.validate_token(token)
