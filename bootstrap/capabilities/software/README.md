# Mac software

This capability migrates small Mac-installed tools while retaining their executable paths. Claude Code and OpenCode use their official installers only when their executable is absent. The in-repo Go programs retain daily dependency maintenance while mise's content-aware task cache owns build freshness. Work's Pi uses mise's GitHub backend and normal release-age policy, retaining the full release tree behind the stable libexec link.

Host reconciliation runs the Go projects' own `install` and `deps:update` tasks with `--skip-tools`, preserving the host-owned Go already on `PATH` and never installing developer tooling. Running those tasks directly in a project still uses its declared Go and golangci-lint versions.

`uvc-util` deliberately uses a narrow Git adapter. Mise's repository resource rejects the four generated overlays this checkout must retain, and its `main` ref does not always fetch a newly advanced remote tracking branch. The adapter preserves untracked files, rejects tracked dirt, origin changes, and divergence, and only fast-forwards fetched `origin/main`. Native task source hashing owns rebuilding; reconciliation never runs camera settings.

Checks report planned changes without applying them. Pi checks query release availability; UVC checks use `git ls-remote` without fetching. If the remote commit is absent locally, the check reports the changed ref but cannot prove ancestry until apply fetches it. Invalid repositories and failed discovery still fail the check.

Run `mise berkeley-mono` on either Mac or `mise docker-context` on the personal Mac; add `--check` for a read-only preview. Berkeley Mono reconciliation checks the four licensed OTF destinations before contacting the original personal 1Password account, checks all four archive members and their OpenType signatures before atomically installing only missing files, and never stores the archive in the repository. The Docker context adapter preserves unrelated contexts and Docker configuration while declaring `pod042` as `ssh://pod042`, with that context selected persistently. Both adapters leave converged state untouched.
