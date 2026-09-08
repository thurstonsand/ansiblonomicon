---
status: open
type: grilling
blocked-by: [9, 39, 41]
---

# Revisit chezmoi ownership with mise dotfiles

## Question

Should mise replace chezmoi for user configuration, and which files should remain generated from Ansiblonomicon versus directly edited and synchronized through mise history?

## Timing and standing direction

Deferred near the end of Bunker Rebuild, after cutover acceptance and the backup and agent-platform decisions. Continue using chezmoi and the current ownership model meanwhile. Thurston expects migration may be worthwhile, but has not approved it. Before reopening, allow a few mise bugfix releases beyond the newly released tracking feature in mise 2026.9.2; reassess current documentation, fixes, and limitations rather than treating launch behavior as settled. This is a revisit gate, not a scheduled upgrade or authorization to migrate.

## Candidate shape and decisions to preserve

- A shared, directly edited `.zshrc` could source a platform/profile-controlled `.zshrc.variant`, avoiding duplicated common configuration. Check shell initialization ordering before assuming the variant belongs at the end.
- Generated Claude settings and per-harness user instructions can remain source-managed: Tera for suitable composition, or the existing generation logic adapted to a pure stdout renderer or a dotfiles-apply hook. Tracking does not reverse-render live edits, and background history sync does not run bootstrap or generation hooks.
- Mise tracking declarations could remain owned by Ansiblonomicon, deployed into system/global mise configuration. Live-tracked contents and variants belong to mise's separate history repository; cross-machine sync needs a shared Git origin. Declarations alone cannot reconstruct those contents. Decide explicitly whether this split is acceptable for the repo's recovery model.
- Template sources and live files can share mise history, but its portable repository layout and automatic checkpoints are not ordinary commits into this checkout. Avoid introducing two competing authorities for the same files.
- Review managed blocks/lines, host/profile variants, secrets and transient-history exposure, conflict recovery, and retirement semantics against the actual chezmoi inventory before choosing a migration boundary.

## Exit criteria

Close with a human-approved ownership and recovery model, a decision to migrate or retain chezmoi, and representative verification requirements for shell variants, generated agent configuration, cross-machine synchronization, and fresh-machine recovery. If migration is approved, create a separate implementation ticket; do not migrate while resolving this decision.

## References

- [Discussion and deferred direction](https://ampcode.com/threads/T-01a07e91-c5bb-75a9-92ae-7db152c640a8)
- [Dotfiles that save themselves](https://jdx.dev/posts/2026-09-07-dotfiles-that-save-themselves/)
- [Mise dotfiles](https://mise.jdx.dev/dotfiles.html), [history and synchronization](https://mise.jdx.dev/history.html), and [templates](https://mise.jdx.dev/templates.html)
- [Operator and agent tooling](40-operator-and-agent-tooling.md): current bootstrap/chezmoi ownership remains in force until explicitly superseded.
