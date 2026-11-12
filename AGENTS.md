# AGENTS.md

Ansiblonomicon is a central store of all of my computer configurations, administered through native mise capabilities and terraform. It strives to be declarative, and reconciles real state towards the configured one in the repo. It covers my personal and work laptops, a NAS, my router, and the Cloudflare edge in front of all of them.

## Project context

See @CONTEXT.md for project vocabulary.

## Ethos

I came here from nix, home-manager, and NixOS. I loved writing configuration once and having it work the same on every machine, and starting afresh with an almost fully configured system. I left because the strictness was stifling: deployed files were read-only, and the language was esoteric. This repo is my way of getting the same outcome by more lenient means, through mise.

- i want developer-focused state in the repo wherever it's practical. Applications that sync their own settings, or keep them somewhere awkward like plists, can stay out; don't contort the repo to chase them
- lean first on platform-native behavior, whether at the OS, harness, or vendor level, and fall back to managing our own machinery where not sufficient
- i ride the latest version and fix breakage when it comes; a pin needs a reason
- keep it lean: remove what I don't use, including dead hosts and config, and keep what I do.

## Ground rules

- reconciliation over execution: I want to declare my desired state and have the system align with it; this means minimize one-way operations and make reruns idempotent
- capabilities for clean abstractions: group native mise resources by the system they own; extend the existing owner before adding another
- everything lives in one place and takes one path: one shared file with branches over per-host copies, settings in one system or none, one way to update
- write it once, above any single tool. That holds for machines and for agent harnesses alike: the harness layer exists so I can move to the next hot thing without rebuilding my setup

## Development Guidelines

See @DEV.md for style and commands.
