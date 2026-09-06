from collections.abc import Generator
from contextlib import contextmanager
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys
from typing import Any

import httpx
import pytest

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts/pod042_kvm.py"
SPEC = spec_from_file_location("pod042_kvm", MODULE_PATH)
assert SPEC is not None
assert SPEC.loader is not None
pod042_kvm: Any = module_from_spec(SPEC)
sys.modules[SPEC.name] = pod042_kvm
SPEC.loader.exec_module(pod042_kvm)


class RecordingConnection:
    def __init__(self) -> None:
        self.messages: list[bytes] = []

    def send(self, message: bytes) -> None:
        self.messages.append(message)


def response(payload: object, status: int = 200) -> httpx.Response:
    return httpx.Response(
        status, json=payload, request=httpx.Request("GET", "https://kvm")
    )


def test_response_result_conforms_success() -> None:
    assert pod042_kvm.response_result(
        response({"ok": True, "result": {"hostname": "pod042-kvm"}}),
        "hostname",
    ) == {"hostname": "pod042-kvm"}


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("ctrl", "ControlLeft"),
        ("A", "KeyA"),
        ("7", "Digit7"),
        ("f12", "F12"),
        ("ArrowUp", "ArrowUp"),
    ],
)
def test_key_code(name: str, expected: str) -> None:
    assert pod042_kvm.key_code(name) == expected


def test_key_code_rejects_unknown_name() -> None:
    with pytest.raises(pod042_kvm.KvmError, match="unknown key name"):
        pod042_kvm.key_code("surely-not-a-key")


def test_parse_chord_rejects_repeated_key() -> None:
    with pytest.raises(pod042_kvm.KvmError, match="cannot repeat"):
        pod042_kvm.parse_chord("ctrl+control")


def test_key_frame_uses_glkvm_binary_protocol() -> None:
    assert pod042_kvm.key_frame("Delete", True) == b"\x01\x01Delete"
    assert pod042_kvm.key_frame("Delete", False) == b"\x01\x00Delete"


def test_send_chord_releases_keys_in_reverse_order() -> None:
    connection = RecordingConnection()

    pod042_kvm.send_chord(
        connection,
        ["ControlLeft", "AltLeft", "Delete"],
        delay=0,
    )

    assert connection.messages == [
        b"\x01\x01ControlLeft",
        b"\x01\x01AltLeft",
        b"\x01\x01Delete",
        b"\x01\x00Delete",
        b"\x01\x00AltLeft",
        b"\x01\x00ControlLeft",
    ]


def test_send_chord_releases_pressed_keys_after_error() -> None:
    class FailingConnection(RecordingConnection):
        def send(self, message: bytes) -> None:
            if message == b"\x01\x01Delete":
                raise RuntimeError("connection dropped")
            super().send(message)

    connection = FailingConnection()

    with pytest.raises(RuntimeError, match="connection dropped"):
        pod042_kvm.send_chord(
            connection,
            ["ControlLeft", "AltLeft", "Delete"],
            delay=0,
        )

    assert connection.messages[-2:] == [
        b"\x01\x00AltLeft",
        b"\x01\x00ControlLeft",
    ]


def test_screenshot_retries_temporary_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    responses = [
        httpx.Response(503),
        httpx.Response(200, content=b"not a jpeg"),
        httpx.Response(200, content=b"\xff\xd8complete jpeg\xff\xd9"),
    ]

    def handler(_: httpx.Request) -> httpx.Response:
        return responses.pop(0)

    client = pod042_kvm.KvmClient("https://kvm")
    client.http.close()
    client.http = httpx.Client(
        base_url="https://kvm", transport=httpx.MockTransport(handler)
    )

    stream_demand = RecordingConnection()
    stream_demand_lifecycle: list[str] = []

    @contextmanager
    def key_socket() -> Generator[RecordingConnection]:
        stream_demand_lifecycle.append("opened")
        try:
            yield stream_demand
        finally:
            stream_demand_lifecycle.append("closed")

    def no_sleep(_: float) -> None:
        pass

    monkeypatch.setattr(client, "key_socket", key_socket)
    monkeypatch.setattr(pod042_kvm.time, "sleep", no_sleep)

    assert client.screenshot() == b"\xff\xd8complete jpeg\xff\xd9"
    assert responses == []
    assert stream_demand_lifecycle == ["opened", "closed"]
    client.http.close()


def test_run_screenshot_writes_returned_frame(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    frame = b"jpeg frame"

    class FakeClient:
        def __init__(self, _: str) -> None:
            pass

        def __enter__(self) -> FakeClient:
            return self

        def __exit__(self, *_: object) -> None:
            pass

        def screenshot(self) -> bytes:
            return frame

    monkeypatch.setattr(pod042_kvm, "KvmClient", FakeClient)
    path = tmp_path / "frame.jpg"

    assert pod042_kvm.run(["screenshot", str(path)]) == 0
    assert path.read_bytes() == frame


def test_run_key_sends_each_chord(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = RecordingConnection()

    class FakeClient:
        def __init__(self, _: str) -> None:
            pass

        def __enter__(self) -> FakeClient:
            return self

        def __exit__(self, *_: object) -> None:
            pass

        @contextmanager
        def key_socket(self) -> Generator[RecordingConnection]:
            yield connection

    monkeypatch.setattr(pod042_kvm, "KvmClient", FakeClient)

    assert pod042_kvm.run(["key", "ctrl+c", "enter", "--delay", "0"]) == 0
    assert connection.messages == [
        b"\x01\x01ControlLeft",
        b"\x01\x01KeyC",
        b"\x01\x00KeyC",
        b"\x01\x00ControlLeft",
        b"\x01\x01Enter",
        b"\x01\x00Enter",
    ]


def test_media_upload_sends_raw_image_with_declared_length(tmp_path: Path) -> None:
    image = tmp_path / "test.iso"
    image.write_bytes(b"iso contents")
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "ok": True,
                "result": {"image": "test.iso", "size": 12, "written": 12},
            },
        )

    client = pod042_kvm.KvmClient("https://kvm")
    client.http.close()
    client.http = httpx.Client(
        base_url="https://kvm", transport=httpx.MockTransport(handler)
    )

    assert client.media_upload(image) == {
        "image": "test.iso",
        "size": 12,
        "written": 12,
    }
    assert requests[0].url.path == "/api/msd/write"
    assert requests[0].url.params["image"] == "test.iso"
    assert requests[0].url.params["remove_incomplete"] == "true"
    assert requests[0].headers["content-length"] == "12"
    assert requests[0].content == b"iso contents"
    client.http.close()


def test_media_mount_selects_image_before_connecting() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"ok": True, "result": {}})

    client = pod042_kvm.KvmClient("https://kvm")
    client.http.close()
    client.http = httpx.Client(
        base_url="https://kvm", transport=httpx.MockTransport(handler)
    )

    client.media_mount("test.iso", cdrom=True, writable=False)

    assert [request.url.path for request in requests] == [
        "/api/msd/set_params",
        "/api/msd/set_connected",
    ]
    assert dict(requests[0].url.params) == {
        "image": "test.iso",
        "cdrom": "true",
        "rw": "false",
    }
    assert dict(requests[1].url.params) == {"connected": "true"}
    client.http.close()


@pytest.mark.parametrize("enabled", [True, False])
def test_media_enable_configures_both_usb_storage_functions(enabled: bool) -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"ok": True, "result": {}})

    client = pod042_kvm.KvmClient("https://kvm")
    client.http.close()
    client.http = httpx.Client(
        base_url="https://kvm", transport=httpx.MockTransport(handler)
    )

    client.media_enable(enabled)

    value = str(enabled).lower()
    assert requests[0].url.path == "/api/system/otg_functions"
    assert dict(requests[0].url.params) == {
        "start_cdrom": value,
        "start_flash": value,
    }
    client.http.close()


def test_run_rejects_writable_cdrom(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeClient:
        def __init__(self, _: str) -> None:
            pass

        def __enter__(self) -> FakeClient:
            return self

        def __exit__(self, *_: object) -> None:
            pass

    monkeypatch.setattr(pod042_kvm, "KvmClient", FakeClient)

    with pytest.raises(pod042_kvm.KvmError, match="requires --disk"):
        pod042_kvm.run(["media", "mount", "test.iso", "--writable"])
