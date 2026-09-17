from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from jinja2 import StrictUndefined
from jinja2.nativetypes import NativeEnvironment
import pytest
import yaml

SENSOR = yaml.safe_load(
    (
        Path(__file__).resolve().parents[1]
        / "docs/operations/house-dashboard/trash-pickup-template.yaml"
    ).read_text()
)[0]["sensor"][0]


def render_reminder(instant: str, current: str, upcoming: str) -> dict[str, object]:
    pickups = {
        "sensor.trash_pickup_current_pickup": SimpleNamespace(
            state=current, attributes={"pickup_types": ["Garbage"]}
        ),
        "sensor.trash_pickup_next_pickup": SimpleNamespace(
            state=upcoming, attributes={"pickup_types": ["Garbage", "Recycling"]}
        ),
    }

    def states(entity_id: str) -> str:
        return pickups[entity_id].state

    def has_value(entity_id: str) -> bool:
        return states(entity_id) not in ("unknown", "unavailable")

    def expand(*entity_ids: str) -> list[SimpleNamespace]:
        return [pickups[entity_id] for entity_id in entity_ids]

    environment = NativeEnvironment(undefined=StrictUndefined)
    result: dict[str, object] = {
        field: environment.from_string(SENSOR[field]).render(
            now=lambda: datetime.fromisoformat(instant).astimezone(
                ZoneInfo("America/New_York")
            ),
            timedelta=timedelta,
            states=states,
            has_value=has_value,
            expand=expand,
        )
        for field in ("availability", "state", "attributes")
    }
    result["state"] = str(result["state"]).strip()
    return result


@pytest.mark.parametrize(
    ("instant", "state", "date", "types"),
    [
        ("2026-09-22T03:59:59+00:00", "hidden", None, []),
        (
            "2026-09-22T04:00:00+00:00",
            "tomorrow",
            "2026-09-23",
            ["Garbage", "Recycling"],
        ),
        (
            "2026-09-23T03:59:59+00:00",
            "tomorrow",
            "2026-09-23",
            ["Garbage", "Recycling"],
        ),
        ("2026-09-23T04:00:00+00:00", "today", "2026-09-23", ["Garbage", "Recycling"]),
        ("2026-09-24T03:59:59+00:00", "today", "2026-09-23", ["Garbage", "Recycling"]),
        ("2026-09-24T04:00:00+00:00", "hidden", None, []),
    ],
)
def test_local_date_window_with_stale_current_pickup(
    instant: str, state: str, date: str | None, types: list[str]
) -> None:
    assert render_reminder(instant, "2026-09-16", "2026-09-23") == {
        "availability": True,
        "state": state,
        "attributes": {"pickup_date": date, "pickup_types": types},
    }


def test_current_pickup_wins_over_tomorrows_different_streams() -> None:
    assert render_reminder("2026-09-23T12:00:00-04:00", "2026-09-23", "2026-09-24") == {
        "availability": True,
        "state": "today",
        "attributes": {"pickup_date": "2026-09-23", "pickup_types": ["Garbage"]},
    }


def test_garbage_only_tomorrow_and_dst_pickup_day() -> None:
    assert render_reminder("2026-10-31T23:59:59-04:00", "2026-11-01", "2026-11-08") == {
        "availability": True,
        "state": "tomorrow",
        "attributes": {"pickup_date": "2026-11-01", "pickup_types": ["Garbage"]},
    }
    assert render_reminder("2026-11-02T04:30:00+00:00", "2026-11-01", "2026-11-08") == {
        "availability": True,
        "state": "today",
        "attributes": {"pickup_date": "2026-11-01", "pickup_types": ["Garbage"]},
    }


@pytest.mark.parametrize("missing", ["unknown", "unavailable"])
def test_provider_outage_is_unavailable_not_a_valid_hidden_schedule(
    missing: str,
) -> None:
    result = render_reminder("2026-09-23T12:00:00-04:00", missing, missing)
    assert result["availability"] is False
    assert result["attributes"] == {"pickup_date": None, "pickup_types": []}
