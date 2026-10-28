#!/usr/bin/env python3
"""Run the actual Compose stack against synthetic inputs, never production sources."""

import argparse
from datetime import UTC, datetime, timedelta
import http.client
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
from typing import Any, cast
from urllib.parse import urlencode
from urllib.request import urlopen
from uuid import uuid4


def get_json(url: str) -> dict[str, Any]:
    with urlopen(url, timeout=10) as response:
        return cast(dict[str, Any], json.load(response))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--keep", action="store_true", help="Keep the synthetic preview for inspection"
    )
    args = parser.parse_args()
    source = Path(__file__).resolve().parent
    root = Path(tempfile.mkdtemp(prefix="observability-smoke-"))
    project = f"observability-smoke-{uuid4().hex[:8]}"
    for name in (
        "compose.yaml",
        "loki.yaml",
        "config.alloy",
        "datasources.yaml",
        "cpa_collector.py",
        "test_cpa_collector.py",
    ):
        shutil.copyfile(source / name, root / name)
    for name in ("loki", "alloy", "cpa", "grafana", "bridge"):
        (root / name).mkdir(mode=0o700)
    (root / "key").write_text("fixture-key")
    (root / "key").chmod(0o600)
    record = root / "bridge/records.jsonl"

    def write_bridge(request: str, read: int, write: int, timestamp: datetime) -> None:
        with record.open("a") as stream:
            stream.write(
                json.dumps(
                    {
                        "event": "request_complete",
                        "timestamp": timestamp.isoformat(),
                        "requestId": request,
                        "runtimeId": "runtime-1",
                        "threadId": "T-smoke",
                        "requestKind": "keyed",
                        "servedModel": "claude-opus-5-5",
                        "outcome": "success",
                        "reason": "compatible",
                        "usage": {
                            "input": 2,
                            "cache_read": read,
                            "cache_creation": write,
                            "output": 11,
                        },
                        "executions": [{"event": "query_reused", "queryId": "query-1"}],
                    }
                )
                + "\n"
            )

    write_bridge("bridge-1", 800, 200, datetime.now(UTC) - timedelta(hours=6))
    (root / "bridge/prompts.jsonl").write_text(
        '{"prompt":"private-prompt-do-not-store"}\n'
    )
    user = f"{os.getuid()}:{os.getgid()}"
    override = {
        "services": {
            **{
                name: {"user": user, "restart": "no"}
                for name in ("loki", "alloy", "grafana", "cpa-collector")
            },
            "loki": {"user": user, "restart": "no", "ports": ["127.0.0.1:0:3100"]},
            "cpa-fixture": {
                "image": "python:3.13-alpine",
                "user": user,
                "command": ["python", "-B", "/app/test_cpa_collector.py", "--serve"],
                "volumes": [f"{root}:/app:ro"],
                "networks": ["ingress"],
            },
            "cpa-collector": {
                "user": user,
                "restart": "no",
                "depends_on": ["cpa-fixture"],
            },
        },
        "networks": {"ingress": {"external": False, "internal": True}},
    }
    (root / "smoke.json").write_text(json.dumps(override))
    env = {
        **os.environ,
        "OBSERVABILITY_STATE_DIR": str(root),
        "DOPPELCLAUDE_DIAGNOSTICS_DIR": str(root / "bridge"),
        "CPA_MANAGEMENT_KEY_FILE": str(root / "key"),
        "CPA_USAGE_URL": "http://cpa-fixture:8317/usage?count=1000",
        "OBSERVABILITY_INGRESS_NETWORK": f"{project}-fixture",
        "GRAFANA_PORT": "0",
    }

    def compose(*arguments: str) -> str:
        result = subprocess.run(
            [
                "docker",
                "compose",
                "-p",
                project,
                "-f",
                str(root / "compose.yaml"),
                "-f",
                str(root / "smoke.json"),
                *arguments,
            ],
            env=env,
            text=True,
            capture_output=True,
        )
        if result.returncode:
            raise RuntimeError(result.stdout + result.stderr)
        return result.stdout.strip()

    try:
        (root / "resolved.json").write_text(compose("config", "--format", "json"))
        compose("up", "-d", "--wait", "--wait-timeout", "180")
        loki = f"http://{compose('port', 'loki', '3100')}"
        grafana = f"http://{compose('port', 'grafana', '3000')}"

        def query(expression: str) -> list[dict[str, Any]]:
            return cast(
                list[dict[str, Any]],
                get_json(
                    loki
                    + "/loki/api/v1/query_range?"
                    + urlencode(
                        {
                            "query": expression,
                            "since": "24h",
                            "limit": "1000",
                            "direction": "forward",
                        }
                    )
                )["data"]["result"],
            )

        def wait_for_request(request: str) -> None:
            deadline = time.monotonic() + 90
            while time.monotonic() < deadline:
                try:
                    if query(
                        '{service_name=~"doppelclaude|cli-proxy-api"} |= "'
                        + request
                        + '"'
                    ):
                        return
                except (OSError, http.client.HTTPException):
                    pass
                time.sleep(1)
            raise AssertionError(f"Loki did not receive {request}")

        wait_for_request("bridge-1")
        wait_for_request("cpa:execution-1")
        # Query through Grafana too: its provisioned datasource must actually work.
        proxied = get_json(
            grafana + "/api/datasources/proxy/uid/loki/loki/api/v1/labels"
        )
        assert "service_name" in proxied["data"], proxied
        print("PASS: bridge file and destructive CPA queue reached Loki through Alloy")
        compose("restart", "loki", "alloy", "cpa-collector")
        loki = f"http://{compose('port', 'loki', '3100')}"
        compose(
            "exec",
            "-T",
            "cpa-fixture",
            "python",
            "-c",
            "from urllib.request import Request, urlopen; "
            "urlopen(Request('http://127.0.0.1:8317/usage', method='POST'))",
        )
        wait_for_request("cpa:execution-2")
        write_bridge("bridge-2", 950, 50, datetime.now(UTC))
        wait_for_request("bridge-2")
        record.rename(root / "bridge/records.jsonl.1")
        write_bridge("bridge-3", 990, 10, datetime.now(UTC))
        wait_for_request("bridge-3")
        streams = query('{service_name=~"doppelclaude|cli-proxy-api"}')
        entries = [json.loads(row[1]) for stream in streams for row in stream["values"]]
        bridge = [row for row in entries if row.get("event") == "request_complete"]
        cpa = [row for row in entries if row.get("event") == "usage"]
        assert sorted(row["requestId"] for row in bridge) == [
            "bridge-1",
            "bridge-2",
            "bridge-3",
        ], bridge
        assert sorted(row["event_id"] for row in cpa) == [
            "cpa:execution-1",
            "cpa:execution-2",
        ], cpa
        assert cpa[0]["usage"] == {
            "input": 3,
            "cache_read": 80,
            "cache_creation": 17,
            "output": 27,
        }, cpa
        assert "do-not-store" not in json.dumps(streams), streams
        assert sum(row["usage"]["cache_read"] for row in bridge) == 2740
        assert sum(row["usage"]["cache_creation"] for row in bridge) == 260
        totals = get_json(
            loki
            + "/loki/api/v1/query?"
            + urlencode(
                {
                    "query": 'sum by (thread_id) (sum_over_time({service_name="doppelclaude"}'
                    ' | json | event="request_complete" | outcome="success"'
                    ' | unwrap usage_cache_read | __error__="" [24h]))'
                }
            )
        )["data"]["result"]
        assert len(totals) == 1 and totals[0]["metric"] == {"thread_id": "T-smoke"}, (
            totals
        )
        assert totals[0]["value"][1] == "2740", totals
        labels = get_json(loki + "/loki/api/v1/labels")["data"]
        assert not {"thread_id", "runtime_id", "request_id", "filename"}.intersection(
            labels
        ), labels
        print(
            "PASS: restart + rotation retained three bridge records and collected a second CPA execution"
        )
        print(
            "PASS: 2,740 bridge cache reads / 260 writes; CPA 3 uncached / 80 read / 17 write / 27 output"
        )
        print("PASS: secrets and prompt dictionary excluded; IDs are not index labels")
        print(f"Grafana: {grafana}; Loki: {loki}")
        if args.keep:
            print(f"Synthetic preview retained: {root}")
            print(f"Cleanup: docker compose -p {project} -f {root}/resolved.json down")
    except BaseException:
        print(compose("logs", "--tail", "35"))
        raise
    finally:
        if not args.keep:
            compose("down", "--volumes")
            shutil.rmtree(root)


if __name__ == "__main__":
    main()
