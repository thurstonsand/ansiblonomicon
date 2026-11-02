"""Build a local, attributed SVG catalogue for the disconnected icon studio."""

import argparse
import json
from pathlib import Path
import re
from typing import TypedDict
import urllib.request
import xml.etree.ElementTree as ET

MDI = "https://raw.githubusercontent.com/iconify/icon-sets/ff91f5f9c3b1ffad7f3e91f7f7f8c739edd57544/json/mdi.json"
HUE = "https://raw.githubusercontent.com/arallsopp/hass-hue-icons/4604f9ad40f251f829da9ac27a82dac74666742c/dist/hass-hue-icons.js"
GROUPS = {
    "floor": [
        "house:floor-lamp-full-shade",
        "hue:signe-gradient-floor",
        "hue:signe",
        "hue:floor-shade",
        "hue:floor-lantern",
        "mdi:floor-lamp",
        "mdi:floor-lamp-torchiere",
    ],
    "table": [
        "hue:signe-gradient-table",
        "hue:table-shade",
        "mdi:lamp",
        "mdi:lamp-outline",
        "mdi:desk-lamp",
    ],
    "wash": ["hue:floor-spot", "hue:play-bar-v", "hue:play-bar", "mdi:spotlight"],
    "ceiling": [
        "mdi:chandelier",
        "mdi:ceiling-light",
        "mdi:light-recessed",
        "hue:pendant-round",
        "mdi:vanity-light",
    ],
    "string": ["mdi:string-lights"],
    "bulb": ["mdi:lightbulb"],
    "art": ["mdi:cloud-outline", "mdi:image-frame", "hue:gradient-lightstrip"],
    "iris": ["hue:iris"],
}

# Model identities come from HA's device registry; generic bulbs don't identify their shades.
LIGHTS = {
    "light.basement_under_main_bedroom_front_bulb": (
        "mdi:lightbulb",
        "bulb",
        "Bare bulb, confirmed by Thurston.",
    ),
    "light.basement_under_main_bedroom_rear_bulb": (
        "mdi:lightbulb",
        "bulb",
        "Bare bulb, confirmed by Thurston.",
    ),
    "light.basement_under_living_room_left_bulb": (
        "mdi:lightbulb",
        "bulb",
        "Bare bulb, confirmed by Thurston.",
    ),
    "light.basement_under_living_room_right_bulb": (
        "mdi:lightbulb",
        "bulb",
        "Bare bulb, confirmed by Thurston.",
    ),
    "light.basement_entryway_front_bulb": (
        "mdi:lightbulb",
        "bulb",
        "Bare bulb, confirmed by Thurston.",
    ),
    "light.basement_entryway_rear_bulb": (
        "mdi:lightbulb",
        "bulb",
        "Bare bulb, confirmed by Thurston.",
    ),
    "light.basement_under_kitchen_front_bulb": (
        "mdi:lightbulb",
        "bulb",
        "Bare bulb, confirmed by Thurston.",
    ),
    "light.basement_under_kitchen_rear_bulb": (
        "mdi:lightbulb",
        "bulb",
        "Bare bulb, confirmed by Thurston.",
    ),
    "light.screened_porch_string_lights": (
        "mdi:string-lights",
        "string",
        "Confirmed Festavia bulb string light.",
    ),
    "light.main_bedroom_fluff_floor_lamp": (
        "hue:floor-lantern",
        "floor",
        "Hue color bulb; lantern shade guessed from Fluff Floor Lamp.",
    ),
    "light.main_bedroom_yanie_fluff_lamp": (
        "hue:table-shade",
        "table",
        "Hue candle bulb; table shade guessed from Fluff Lamp.",
    ),
    "light.main_bedroom_thurston_fluff_lamp": (
        "hue:table-shade",
        "table",
        "Hue candle bulb; table shade guessed from Fluff Lamp.",
    ),
    "light.main_bedroom_cloud_painting": (
        "mdi:cloud-outline",
        "art",
        "Confirmed OmniGlow striplight; cloud represents the named artwork.",
    ),
    "light.living_room_floor_light_left": (
        "hue:signe-gradient-floor",
        "floor",
        "Confirmed Signe gradient floor.",
    ),
    "light.living_room_floor_light_right": (
        "hue:signe-gradient-floor",
        "floor",
        "Confirmed Signe gradient floor.",
    ),
    "light.living_room_wall_wash_right": (
        "hue:floor-spot",
        "wash",
        "Confirmed Hue Play wall washer; closest silhouette, not the older Play bar.",
    ),
    "light.living_room_front_right_floor_lamp": (
        "hue:floor-shade",
        "floor",
        "Eve-controlled floor lamp; shade guessed from its name.",
    ),
    "light.living_room_rear_center_floor_lamp": (
        "hue:floor-shade",
        "floor",
        "Eve-controlled floor lamp; shade guessed from its name.",
    ),
    "light.main_bath_vanity_lights": (
        "mdi:vanity-light",
        "ceiling",
        "Inovelli-controlled vanity; fixture inferred from its name.",
    ),
    "light.main_bath_tub_light": (
        "mdi:light-recessed",
        "ceiling",
        "Inovelli-controlled tub light; recessed fixture guessed.",
    ),
    "light.main_floor_w_i_c_lights": (
        "mdi:ceiling-light",
        "ceiling",
        "Inovelli-controlled closet lights; ceiling fixture guessed.",
    ),
    "light.breakfast_nook_blue_lamp": (
        "hue:floor-spot",
        "wash",
        "Hue color spot bulb; spotlight housing guessed.",
    ),
    "light.breakfast_nook_yellow_lamp": (
        "hue:floor-spot",
        "wash",
        "Hue color spot bulb; spotlight housing guessed.",
    ),
    "light.thurston_office_desk_lamp_left": (
        "mdi:desk-lamp",
        "table",
        "Hue color bulb; desk fixture inferred from its name.",
    ),
    "light.thurston_office_desk_lamp_right": (
        "hue:signe-gradient-table",
        "table",
        "Confirmed Signe gradient table, despite its Desk Lamp name.",
    ),
    "light.thurston_office_wall_wash_left": (
        "hue:floor-spot",
        "wash",
        "Confirmed Hue Play wall washer; closest silhouette, not the older Play bar.",
    ),
    "light.thurston_office_wall_wash_right": (
        "hue:floor-spot",
        "wash",
        "Confirmed Hue Play wall washer; closest silhouette, not the older Play bar.",
    ),
    "light.thurston_office_iris": ("hue:iris", "iris", "Confirmed Hue Iris."),
}


class SvgElement(TypedDict):
    tag: str
    attributes: dict[str, str]


class Icon(TypedDict):
    elements: list[SvgElement]
    keywords: list[str]


def build():
    with urllib.request.urlopen(MDI, timeout=30) as response:
        mdi = json.load(response)
    with urllib.request.urlopen(HUE, timeout=30) as response:
        hue = response.read().decode()
    icons: dict[str, Icon] = {}
    for name, icon in mdi["icons"].items():
        tree = ET.fromstring(f"<svg>{icon['body']}</svg>")
        icons[f"mdi:{name}"] = {
            "elements": [
                {"tag": element.tag, "attributes": element.attrib} for element in tree
            ],
            "keywords": [],
        }
    for name, path, keywords in re.findall(
        r'"([a-z0-9-]+)"\s*:\s*\{\s*path:\s*"([^"]+)"\s*,\s*keywords:\s*(\[[^\]]*\])',
        hue,
    ):
        icons[f"hue:{name}"] = {
            "elements": [
                {"tag": "path", "attributes": {"d": path, "fill": "currentColor"}}
            ],
            "keywords": json.loads(keywords),
        }
    if not any(name.startswith("hue:") for name in icons):
        raise ValueError("Hue icon source format changed")
    icons["house:floor-lamp-full-shade"] = {
        "elements": [
            {
                "tag": "path",
                "attributes": {
                    "d": "M7 2H17V22H7Z M8 6V7H16V6Z M8 11V12H16V11Z M8 16V17H16V16Z",
                    "fill": "currentColor",
                    "fill-rule": "evenodd",
                },
            }
        ],
        "keywords": ["tower", "column", "paper", "lantern", "full height", "fluff"],
    }
    return {
        "icons": {name: icons[name] for names in GROUPS.values() for name in names},
        "groups": GROUPS,
        "lights": {
            entity: {"icon": icon, "group": group, "basis": basis}
            for entity, (icon, group, basis) in LIGHTS.items()
        },
        "sources": [
            {
                "name": "Material Design Icons · Pictogrammers",
                "url": "https://pictogrammers.com/library/mdi/",
                "license": "Apache 2.0",
                "license_url": "https://www.apache.org/licenses/LICENSE-2.0",
                "source": MDI,
            },
            {
                "name": "Hue Icons · arallsopp and contributors",
                "url": "https://github.com/arallsopp/hass-hue-icons",
                "license": "CC BY-NC-SA 4.0 · non-commercial",
                "license_url": "https://creativecommons.org/licenses/by-nc-sa/4.0/",
                "source": HUE,
            },
        ],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    catalogue = build()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(catalogue))
    print(f"{len(catalogue['icons'])} icons for {len(catalogue['lights'])} lights")
