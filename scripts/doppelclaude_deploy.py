"""Deploy the Doppelclaude edge proxy and reconcile its secret bindings."""

import json
from pathlib import Path
import subprocess

from worker_secrets import reject_dev_vars, required_secrets

WORKER_DIR = Path(__file__).resolve().parents[1] / "wrangler" / "doppelclaude"


def main() -> None:
    secrets = required_secrets("doppelclaude")
    reject_dev_vars(WORKER_DIR)
    subprocess.run(["wrangler", "deploy"], cwd=WORKER_DIR, check=True)
    subprocess.run(
        ["wrangler", "secret", "bulk"],
        cwd=WORKER_DIR,
        input=json.dumps(secrets),
        text=True,
        check=True,
    )


if __name__ == "__main__":
    main()
