# AGENTS.md

Ansiblonomicon is a central store of all of my computer configurations, administered primarily through ansible, chezmoi, and terraform. It strives to be declarative, and reconciles real state towards the configured one in the repo. It covers my personal and work laptops, a NAS, my router, a dev VM, and the Cloudflare edge in front of all of them.

## Project context

See @CONTEXT.md for project vocabulary.

## Ethos

I used to be a heavy user of nix, home-manager, and NixOS, but I found the strictness of adherence to the config to be stifling (many files deployed as read-only) and I found the language esoteric (tho this is largely solved by agents today). I thought there ought to be a way to achieve the same, but through a different, more lenient means, and stumbled on the combination of ansible and chezmoi. I really liked the ability to write configuration once, and have it deployed and working across all my machines in a consistent way, and that I can start afresh with an almost-fully-configured system with relative ease.

To the extent possible, I want to manage all developer-focused state within the repo. For applications, where relevant we can capture it here, but for many they store their own settings via cloud sync, or simply in a means that's not easily accessible as a file (plists...), so it's acceptable to forego those.

I also wanted to capture the various AI agent harnesses in a unified and flexible way, since I found each system different enough to make it worth implementing a layer on top of them. The goal is to let me transition between agents as seamlessly as possible to make it easy to try out the next hot thing.

## Core principles

- reconciliation over execution: I want to declare my desired state and have the system align with it; this means minimize one-way operations and make reruns idempotent
- roles for clean abstractions: save roles for when it's possible to encapsulate an idea or system as an abstraction for its complexity; suggest to the user when a role might be appropriate
- for removals that may need to propagate across systems, prefer `.chezmoiremove` and `.ansibleremove` files to keep state declarative. Do not need to do this if the change was never deployed to a different machine or was still in progress
- on the terminal, I use `cmd` to represent ghostty actions, `ctrl` for shell interactions, and `alt` for whatever is holding the alt-screen. This may not always be universally possible, but is a general rule of thumb

## Development Guidelines

See @DEV.md for style and commands.
