# Mac apps capability helper

`reconcile.py --brewfile PATH [--check]` delegates the exact file path to Homebrew Bundle. It does not rewrite the Brewfile, so arbitrary Ruby, options, sorted local includes, and tap trust semantics remain intact. The caller supplies any already-scoped `SUDO_ASKPASS` value; the helper does not resolve credentials.

Scoped fnox launches carry profile, selected-key, and pinned-Python metadata in `HOMEBREW_ANSIBLONOMICON_EXEC_{PROFILE,KEYS,PYTHON}`. This is the canonical transport through Homebrew's `env -i` cask boundary, which retains `HOMEBREW_*`; askpass can therefore reuse the validated credential scope without depending on sanitized `PATH` or fetching the password again. Consumers remove all three metadata fields before starting an unscoped child.

Check mode retains Homebrew tap trust enforcement. Untrusted definitions are reported as errors rather than bypassed while checking drift. Like the legacy check, it reports available updates even when the daily interval would defer applying them.

The helper retains the legacy `~/.cache/ansible-homebrew/upgrade.stamp` behavior. A missing stamp or one at least 24 hours old makes upgrades and cleanup due. A newer stamp adds `--no-upgrade`, skips MAS upgrades and cleanup, and remains untouched. The stamp is replaced only after the complete due reconciliation succeeds.

Homebrew's public `bundle list --mas` prints app names rather than IDs. The helper therefore loads `bundle/brewfile` and uses Bundle's private `Homebrew::Bundle::Brewfile.read(file: PATH)` API through `brew ruby`. Parsing happens before `bundle check`, because Bundle uses status 1 for both malformed Brewfiles and ordinary drift. This private API is the compatibility point to revisit if Homebrew provides an ID-bearing public listing format.

Due cleanup is deliberately bounded with the positive `--formula`, `--cask`, and `--tap` selectors. Homebrew combines those selectors, so formulae, casks, and taps are cleaned while Bundle extensions such as MAS, npm, uv, and Go stay outside this capability's cleanup ownership.
