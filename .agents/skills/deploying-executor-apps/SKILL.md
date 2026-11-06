---
name: deploying-executor-apps
description: Deploys the executor.sh apps under `executor/` through the Executor MCP. Use when changing, deploying, or checking drift of an executor app.
---

# Deploying executor apps

`executor/<slug>/` holds the complete source of the executor.sh app with that slug, and is its single source of truth. The app's hosted Git and its active deployment both follow it. Executor's tools document themselves; `describe` them before first use.

## Deploy

Push the change to `executor/<slug>/` to main. The Deploy Executor Apps workflow runs `scripts/deploy-executor-apps.sh`, which commits each app's directory to its hosted Git and deploys that commit; `workflow_dispatch` reruns it. It authenticates with the `EXECUTOR_ACCESS_TOKEN` secret, Thurston's personal access token scoped to the organization.

Verify through the Executor MCP: `apps.source` reports the new deployment with `sourceCommit` equal to the workflow's commit, `search` lists the app's tools under `tools.<slug>.`, and one read-only tool call returns real data.

Every deploy goes through a commit. A deploy from loose files leaves the hosted Git behind what runs, and the next deploy from Git silently brings the old app back.

## Drift

`apps.source` is what runs; `appManagement.source` is the hosted Git. Both should equal `executor/<slug>/` byte for byte, and the active deployment's `sourceCommit` should be the hosted Git's commit. When they differ, the repo wins: rerun the workflow.
