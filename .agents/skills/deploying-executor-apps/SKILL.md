---
name: deploying-executor-apps
description: Deploys the executor.sh apps under `executor/` through the Executor MCP. Use when changing, deploying, or checking drift of an app such as `executor/pod153`.
---

# Deploying executor apps

`executor/<slug>/` holds the complete source of the executor.sh app with that slug, and is its single source of truth. The app's hosted Git and its active deployment both follow it. Executor's tools document themselves; `describe` them before first use.

## Deploy

1. Commit the change to `executor/<slug>/` in this repo.
2. Find the app's ID with `appManagement.list` by slug, then read its working source with `appManagement.source` and note `revision.commit`.
3. Save the repo's files with `appManagement.commit`, passing that commit as `expected` and every file under `executor/<slug>/`. Check `removed` against what the repo change deleted.
4. Deploy that commit with `appManagement.deploy` and `{ commit }`.
5. Verify: `apps.source` reports the new deployment with `sourceCommit` equal to your commit, `search` lists the app's tools under `tools.<slug>.`, and one read-only tool call returns real data.

Always deploy a commit. A deploy from loose files leaves the hosted Git behind what runs, and the next deploy from Git silently brings the old app back.

## Drift

`apps.source` is what runs; `appManagement.source` is the hosted Git. Both should equal `executor/<slug>/` byte for byte, and the active deployment's `sourceCommit` should be the hosted Git's commit. When they differ, the repo wins: run the deploy steps from step 2.
