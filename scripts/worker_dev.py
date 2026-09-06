#!/usr/bin/env python3
"""Run a local Worker with current canonical secrets, without credential files."""

import argparse
import os
from pathlib import Path
import sys

from worker_secrets import WORKER_BINDINGS, reject_dev_vars, required_secrets

ROOT_DIR = Path(__file__).resolve().parent.parent


def main(worker: str, port: int) -> int:
    worker_dir = ROOT_DIR / "wrangler" / worker
    try:
        secrets = required_secrets(worker)
        reject_dev_vars(worker_dir)
    except ValueError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    # Wrangler binds every process variable in this mode. Do not expose the host's
    # other credentials or Cloudflare deployment authority to the local Worker.
    env = {
        name: os.environ[name]
        for name in ("PATH", "HOME", "TMPDIR", "SYSTEMROOT", "NODE_EXTRA_CA_CERTS")
        if name in os.environ
    }
    env.update(secrets)
    env["CLOUDFLARE_INCLUDE_PROCESS_ENV"] = "true"
    env["WRANGLER_SEND_METRICS"] = "false"
    os.chdir(worker_dir)
    os.execvpe(
        "wrangler",
        [
            "wrangler",
            "dev",
            "--local",
            "--ip",
            "127.0.0.1",
            "--port",
            str(port),
            "--env-file",
            os.devnull,
        ],
        env,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("worker", choices=WORKER_BINDINGS)
    parser.add_argument("--port", type=int, default=8787)
    args = parser.parse_args()
    sys.exit(main(args.worker, args.port))
