# UVC Camera Configuration

## Project Layout

- `src/uvc-util`: compiled CLI for UVC controls (uses IOKit on macOS)
- `~/.local/bin/configure_camera.py`: Python script that detects devices and applies settings
- `~/.local/bin/camera_settings.json`: per-camera configuration file
- `uvc-util.xcodeproj/` and `src/*.m`: sources for building `uvc-util`

## uvc-util CLI

### Device Discovery

- `--list-devices`: list connected UVC devices (index, vendor:product, name)
- Target selection: `-V <vendor-id>:<product-id>`, `-I <index>`, `-L <location-id>`, `-N <name>`

### Controls

- `--list-controls`: list available controls for the selected device
- `--show-control=<control>`: show type, range, step, default
- Get/set: `--get[-value]=<control>`, `--set=<control>=<value>`

## Python Script (`configure_camera.py`)

- Detects devices using `--list-devices`
- Matches devices by `vendor:product` key in JSON
- Continues on error per `keep_running` flag
- Environment variables:
  - `UVC_UTIL`: path to `uvc-util` binary (default: `~/.local/opt/uvc-util/src/uvc-util`)
  - `UVC_SETTINGS_FILE`: path to settings JSON (default: same directory as script)

## JSON Settings Format (`camera_settings.json`)

### Root Keys

- `keep_running` (boolean): continue applying settings even if one fails
- `cameras` (object): keys are lowercase `vendor:product` IDs

### Per-Camera Object

- `name` (string, optional): human-readable name
- `controls` (object): `{ "control-name": value, ... }`

### Value Encoding

- booleans: `true`/`false`
- numbers: integers/floats
- strings: passed as-is (supports `"default"`, `"minimum"`, `"maximum"`)
- multi-component controls: object → `{key=value,...}` (e.g. `{ "pan": 0, "tilt": 0 }`)

## Typical Workflows

1. Discover vendor:product IDs: `uvc-util --list-devices`
2. Inspect controls: `uvc-util -V <vp> --list-controls` and `--show-control=<control>`
3. Read current values: `uvc-util -V <vp> --get-value=<control>`
4. Write values to `camera_settings.json`
5. Apply settings: `configure_camera.py`

## Build uvc-util

From `src/` directory:

```bash
gcc -o uvc-util -framework IOKit -framework Foundation uvc-util.m UVCController.m UVCType.m UVCValue.m
```
