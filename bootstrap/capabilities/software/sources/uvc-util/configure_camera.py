#!/usr/bin/env python3
import json
import os
import re
import subprocess
import sys
from typing import NotRequired, TypedDict

# Control values can be scalars or multi-component dicts like {pan: -7200, tilt: 0}
ControlValue = bool | int | str | dict[str, bool | int | str]


class CameraConfig(TypedDict):
    controls: dict[str, ControlValue]


class Settings(TypedDict):
    cameras: dict[str, CameraConfig]
    keep_running: NotRequired[bool]


def run_command(args: list[str]) -> tuple[int, str, str]:
    process = subprocess.Popen(
        args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    stdout, stderr = process.communicate()
    return process.returncode, stdout.strip(), stderr.strip()


def get_uvc_util_path() -> str:
    # Allow override via environment variable; default to ~/.local/opt path
    return os.environ.get(
        "UVC_UTIL",
        os.path.expanduser("~/.local/opt/uvc-util/src/uvc-util"),
    )


def list_devices(uvc_util: str) -> list[dict[str, str]]:
    code, out, err = run_command([uvc_util, "--list-devices"])
    if code != 0:
        raise RuntimeError(f"Failed to list UVC devices: {err or out}")

    devices: list[dict[str, str]] = []
    # Expected lines like:
    # 0            0x2e1a:0x4c04  0x02141000   1.10         Insta360 Link 2
    pattern = re.compile(
        r"^(?P<index>\d+)\s+(?P<vendprod>0x[0-9a-fA-F]+:0x[0-9a-fA-F]+)\s+\S+\s+\S+\s+(?P<name>.+)$"
    )
    for line in out.splitlines():
        line = line.strip()
        match = pattern.match(line)
        if match:
            devices.append(
                {
                    "index": match.group("index"),
                    "vendor_product": match.group("vendprod").lower(),
                    "name": match.group("name").strip(),
                }
            )
    return devices


def set_control(uvc_util: str, selector: list[str], control: str, value: str) -> None:
    args = [uvc_util, *selector, f"--set={control}={value}"]
    code, out, err = run_command(args)
    if code != 0:
        raise RuntimeError(f"Failed setting {control} to {value}: {err or out}")


def value_to_uvc(value: ControlValue) -> str:
    """Convert Python value to uvc-util CLI value string.

    - bool -> "true"/"false"
    - dict -> multi-component value, e.g. {pan=-7200,tilt=0}
    - other scalars -> str(value)
    - strings are passed through as-is (allowing "default", etc.)
    """
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, dict):
        parts: list[str] = []
        for k, v in value.items():
            v_str = ("true" if v else "false") if isinstance(v, bool) else str(v)
            parts.append(f"{k}={v_str}")
        return "{" + ",".join(parts) + "}"
    return str(value)


def load_settings(settings_path: str) -> Settings:
    with open(settings_path, encoding="utf-8") as f:
        data: Settings = json.load(f)
    return data


def apply_camera_settings(
    uvc_util: str, vendor_product: str, camera_cfg: CameraConfig, keep_running: bool
) -> None:
    selector = ["-V", vendor_product]
    controls = camera_cfg.get("controls", {})

    for control_name, control_value in controls.items():
        value_str = value_to_uvc(control_value)
        try:
            set_control(uvc_util, selector, control_name, value_str)
        except Exception as exc:
            if keep_running:
                print(
                    f"Warning: {vendor_product} failed set {control_name}={value_str}: {exc}",
                    file=sys.stderr,
                )
                continue
            raise


def main() -> int:
    uvc_util = get_uvc_util_path()
    if not os.path.isfile(uvc_util):
        print(f"Error: uvc-util not found at {uvc_util}", file=sys.stderr)
        return 1

    script_dir = os.path.dirname(os.path.realpath(__file__))
    settings_path = os.environ.get(
        "UVC_SETTINGS_FILE", os.path.join(script_dir, "camera_settings.json")
    )
    try:
        settings = load_settings(settings_path)
    except Exception as exc:
        print(f"Error loading settings from {settings_path}: {exc}", file=sys.stderr)
        return 1

    keep_running = settings.get("keep_running", True)
    camera_map = settings["cameras"]

    devices = list_devices(uvc_util)
    if not devices:
        print("No UVC devices found.")
        return 0

    any_applied = False
    for device in devices:
        vendprod = device["vendor_product"]
        name = device["name"]
        cfg = camera_map.get(vendprod)
        if cfg is not None:
            print(f"Configuring {name} ({vendprod})...")
            try:
                apply_camera_settings(uvc_util, vendprod, cfg, keep_running)
                print(f"Completed configuration for {name}.")
                any_applied = True
            except Exception as exc:
                print(f"Failed configuring {name}: {exc}", file=sys.stderr)

    if not any_applied:
        print("No known devices connected. Detected devices:")
        for device in devices:
            print(f"- {device['name']} ({device['vendor_product']})")

    return 0


if __name__ == "__main__":
    sys.exit(main())
