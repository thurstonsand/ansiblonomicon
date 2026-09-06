#!/usr/bin/python3
import argparse
import subprocess

POOLS = {
    "ark": {
        "guid": "8619294010601504858",
        "failmode": "wait",
        "autotrim": "off",
        "autoreplace": "off",
    },
    "black-box": {
        "guid": "131852107186480998",
        "failmode": "wait",
        "autotrim": "on",
        "autoreplace": "off",
    },
}


def properties(pool: str) -> dict[str, str]:
    result = subprocess.run(
        [
            "/usr/sbin/zpool",
            "get",
            "-Hp",
            "-o",
            "property,value",
            "guid,failmode,autotrim,autoreplace",
            pool,
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    current = dict(line.split("\t") for line in result.stdout.splitlines())
    if current["guid"] != POOLS[pool]["guid"]:
        raise RuntimeError(
            f"Refusing unexpected pool GUID for {pool}: {current['guid']}"
        )
    return current


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    current = {pool: properties(pool) for pool in POOLS}
    for pool, desired in POOLS.items():
        for prop in ("failmode", "autotrim", "autoreplace"):
            if current[pool][prop] == desired[prop]:
                continue
            print(
                f"{pool}: {prop} {current[pool][prop]} -> {desired[prop]}", flush=True
            )
            if args.apply:
                properties(pool)
                subprocess.run(
                    ["/usr/sbin/zpool", "set", f"{prop}={desired[prop]}", pool],
                    check=True,
                )
                if properties(pool)[prop] != desired[prop]:
                    raise RuntimeError(f"Pool property did not converge: {pool} {prop}")


if __name__ == "__main__":
    main()
