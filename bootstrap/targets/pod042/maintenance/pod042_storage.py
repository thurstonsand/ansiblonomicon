import json
import subprocess
from typing import NotRequired, TypedDict

POOLS = {"ark": "8619294010601504858", "black-box": "131852107186480998"}


class Vdev(TypedDict):
    state: str
    read_errors: int | str
    write_errors: int | str
    checksum_errors: int | str
    vdevs: NotRequired[dict[str, "Vdev"]]


def healthy_vdevs(vdevs: dict[str, Vdev]) -> bool:
    return all(
        vdev["state"] == "ONLINE"
        and int(vdev["read_errors"]) == 0
        and int(vdev["write_errors"]) == 0
        and int(vdev["checksum_errors"]) == 0
        and healthy_vdevs(vdev.get("vdevs", {}))
        for vdev in vdevs.values()
    )


def clean_scrub(pool: str) -> bool:
    result = subprocess.run(
        ["/usr/sbin/zpool", "status", "-jp", pool],
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    status = json.loads(result.stdout)["pools"][pool]
    if status["pool_guid"] != POOLS[pool]:
        raise ValueError(f"Unexpected pool GUID for {pool}")
    scan = status["scan_stats"]
    return (
        status["state"] == "ONLINE"
        and int(status["error_count"]) == 0
        and healthy_vdevs(status["vdevs"])
        and scan["function"] == "SCRUB"
        and scan["state"] == "FINISHED"
        and int(scan["errors"]) == 0
        and int(scan["processed"]) == 0
    )
