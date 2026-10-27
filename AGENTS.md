# AGENTS.md

Ansiblonomicon is a central store of all of my computer configurations, administered through native mise capabilities and terraform. It strives to be declarative, and reconciles real state towards the configured one in the repo. It covers my personal and work laptops, a NAS, my router, and the Cloudflare edge in front of all of them.

## Project context

See @CONTEXT.md for project vocabulary.

## Ethos

I used to be a heavy user of nix, home-manager, and NixOS, but I found the strictness of adherence to the config to be stifling (many files deployed as read-only) and I found the language esoteric (tho this is largely solved by agents today). I thought there ought to be a way to achieve the same, but through a different, more lenient means, and stumbled on mise. I really liked the ability to write configuration once, and have it deployed and working across all my machines in a consistent way, and that I can start afresh with an almost-fully-configured system with relative ease.

To the extent possible, I want to manage all developer-focused state within the repo. For applications, where relevant we can capture it here, but for many they store their own settings via cloud sync, or simply in a means that's not easily accessible as a file (plists...), so it's acceptable to forego those.

I also wanted to capture the various AI agent harnesses in a unified and flexible way, since I found each system different enough to make it worth implementing a layer on top of them. The goal is to let me transition between agents as seamlessly as possible to make it easy to try out the next hot thing.

## Core principles

- reconciliation over execution: I want to declare my desired state and have the system align with it; this means minimize one-way operations and make reruns idempotent
- capabilities for clean abstractions: group native mise resources by the system they own; extend the existing owner before adding another
- on the terminal, I use `cmd` to represent ghostty actions, `ctrl` for shell interactions, and `alt` for whatever is holding the alt-screen. This may not always be universally possible, but is a general rule of thumb

## Development Guidelines

See @DEV.md for style and commands.

## Outstanding on the Omarchy laptops

The `thurstons-voice` skill hands drafts over as `clipcopy:` links, but only the work Mac has a handler for them: `ClipCopy.app`, described in `bootstrap/capabilities/terminal-tools/README.md`. On `type-a-no2` or `no9-type-s`, tell Thurston this is outstanding before starting other work, and when he agrees:

1. In `bootstrap/capabilities/omarchy/`, add a script that percent-decodes everything after `clipcopy:` and pipes it to `wl-copy`, plus a `.desktop` file under `files/applications/` with `MimeType=x-scheme-handler/clipcopy;` whose `Exec` runs that script on `%u`. Link both from `mise.config.toml`, and make the scheme's default handler the `.desktop` file with `xdg-mime`.
2. Reconcile with `mise omarchy -t omarchy-config`. It passes when `xdg-open "clipcopy:<encoded>"` leaves an exact match in `wl-paste` for text with backticks, `$`, quotes, unicode, and blank lines, and when Thurston clicks such a link in pi and it copies without opening a window.
3. In the skill's `SKILL.md.j2`, move the laptops' hostnames into the `copy-link.py` branch and delete their `wl-copy` branch.

The capability is shared, so the second laptop needs only step 2. Delete this section once both pass.
