"""Private, standalone placement editor; never connects to Home Assistant."""

import argparse
import hashlib
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import math
from pathlib import Path
from typing import Any, cast

HERE = Path(__file__).resolve().parent


def inventory(config: dict[str, Any]) -> list[dict[str, str]]:
    devices: list[dict[str, str]] = []
    for floor in config["floors"]:
        for room in floor["rooms"]:
            entities: dict[str, str | None] = dict.fromkeys(room.get("lights", []))
            if room.get("entity"):
                entities[room["entity"]] = room.get("mapNote")
            for appliance in room.get("appliances", []):
                entities[appliance["entity"]] = appliance["name"]
            if room.get("doorbell"):
                entities[room["doorbell"]["camera"]] = "Doorbell camera"
            for thermostat in config["thermostats"]:
                if thermostat["entity"].split(".")[1].startswith(room["id"] + "_"):
                    entities[thermostat["entity"]] = "Thermostat"
            for entity, name in entities.items():
                short = entity.split(".")[1].removeprefix(room["id"] + "_")
                devices.append(
                    {
                        "entity": entity,
                        "name": name or short.replace("_", " ").capitalize(),
                        "room": room["id"],
                        "floor": floor["id"],
                        "kind": entity.split(".")[0].replace("_", " "),
                    }
                )
    return devices


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bind", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8766)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--icons-output", type=Path)
    parser.add_argument("--icon-catalogue", type=Path)
    args = parser.parse_args()
    if bool(args.icons_output) != bool(args.icon_catalogue):
        parser.error("--icons-output and --icon-catalogue must be supplied together")
    config = json.loads((HERE / "dashboard.json").read_text())["views"][0]["cards"][0]
    devices = inventory(config)
    by_entity = {device["entity"]: device for device in devices}
    floors = {floor["id"]: floor for floor in config["floors"]}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    catalogue = None
    if args.icons_output:
        args.icons_output.parent.mkdir(parents=True, exist_ok=True)
        catalogue = json.loads(args.icon_catalogue.read_text())
        if not args.icons_output.exists():
            args.icons_output.write_text(
                json.dumps(
                    {
                        entity: light["icon"]
                        for entity, light in catalogue["lights"].items()
                    },
                    indent=2,
                    sort_keys=True,
                )
                + "\n"
            )

    def saved(path: Path) -> bytes:
        return path.read_bytes() if path.exists() else b"{}"

    def revision(data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

    class Handler(BaseHTTPRequestHandler):
        def respond(
            self, status: int, body: bytes, content_type: str = "application/json"
        ) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path == "/":
                self.respond(
                    200,
                    (HERE / "placement.html").read_bytes(),
                    "text/html; charset=utf-8",
                )
            elif self.path == "/icons" and catalogue:
                self.respond(
                    200,
                    (HERE / "icons.html").read_bytes(),
                    "text/html; charset=utf-8",
                )
            elif self.path == "/api/icon-catalogue" and catalogue:
                self.respond(200, json.dumps(catalogue).encode())
            elif self.path == "/api/icons" and catalogue:
                data = saved(args.icons_output)
                self.respond(
                    200,
                    json.dumps(
                        {
                            "floors": config["floors"],
                            "devices": devices,
                            "placements": config["placements"],
                            "icons": json.loads(data),
                            "revision": revision(data),
                        }
                    ).encode(),
                )
            elif self.path == "/api":
                data = saved(args.output)
                self.respond(
                    200,
                    json.dumps(
                        {
                            "floors": config["floors"],
                            "devices": devices,
                            "placements": json.loads(data),
                            "revision": revision(data),
                        }
                    ).encode(),
                )
            else:
                self.respond(404, b'"Not found"')

        def do_PUT(self):
            icons = self.path == "/api/icons" and catalogue is not None
            if self.path != "/api" and not icons:
                self.respond(404, b'"Not found"')
                return
            field = "icons" if icons else "placements"
            output = args.icons_output if icons else args.output
            origin = self.headers.get("Origin")
            if origin and origin != f"http://{self.headers.get('Host')}":
                self.respond(403, b'"Cross-origin save refused"')
                return
            if self.headers.get("Content-Type") != "application/json":
                self.respond(415, b'"Expected application/json"')
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 65536:
                    raise ValueError("Invalid request size")
                raw: object = json.loads(self.rfile.read(length))
                if not isinstance(raw, dict):
                    raise ValueError(f"Expected {field} object")
                payload = cast(dict[str, Any], raw)
                if not isinstance(payload.get(field), dict):
                    raise ValueError(f"Expected {field} object")
                choices: dict[str, Any] = payload[field]
                for entity, point in choices.items():
                    if icons and catalogue is not None:
                        if (
                            entity not in by_entity
                            or not isinstance(point, str)
                            or point not in catalogue["icons"]
                        ):
                            raise ValueError("Unknown device or icon")
                        continue
                    if entity not in by_entity or not isinstance(point, dict):
                        raise ValueError("Unknown device or invalid placement")
                    point = cast(dict[str, Any], point)
                    device = by_entity[entity]
                    if set(point) != {"floor", "room", "x", "y"} or any(
                        point[key] != device[key] for key in ("floor", "room")
                    ):
                        raise ValueError(
                            "Placement must keep its configured room and floor"
                        )
                    floor = floors[device["floor"]]
                    for axis, limit in (("x", floor["width"]), ("y", floor["height"])):
                        value = point[axis]
                        if (
                            type(value) not in (int, float)
                            or not math.isfinite(value)
                            or not 0 <= value <= limit
                        ):
                            raise ValueError(
                                "Coordinates must lie within the floor plan"
                            )
            except (ValueError, UnicodeDecodeError) as error:
                self.respond(400, json.dumps(str(error)).encode())
                return
            if payload.get("revision") != revision(saved(output)):
                self.respond(
                    409,
                    b'"Choices changed in another window. Download your draft, then reload before merging."',
                )
                return
            data = (
                json.dumps(payload[field], indent=2, sort_keys=True) + "\n"
            ).encode()
            temporary = output.with_suffix(".tmp")
            temporary.write_bytes(data)
            temporary.replace(output)
            self.respond(200, json.dumps({"revision": revision(data)}).encode())

    server = HTTPServer((args.bind, args.port), Handler)
    print(
        f"Placement editor ready at http://{args.bind}:{args.port} — saves to {args.output}",
        flush=True,
    )
    server.serve_forever()


if __name__ == "__main__":
    main()
