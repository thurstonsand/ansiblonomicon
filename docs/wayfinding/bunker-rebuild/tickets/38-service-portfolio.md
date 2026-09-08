---
status: closed
type: grilling
blocked-by: [31, 34, 36, 37]
claimed: T-01a0790a-aa41-7258-b0fd-c559a15e473a
---

# Service portfolio

## Question

Audit every service the old pod042 playbook and stack inventory would start. Decide which services still belong on the rebuilt host, what user-visible contract each retains, what can merge or disappear, and which dependencies or data paths change under `ark`, `black-box`, one Caddy gateway, and the new trust domains.

Home Assistant is planned as a VM on pod042 and has not been started. Defer its HTTPS/MCP connectivity checks until that VM is deployed; the unavailable endpoint is not a credential-migration regression.

Do not implement stacks in this ticket. Each retained service or tightly coupled service group graduates into its own desired-state signoff ticket, followed by a separate implementation ticket.

The fnox migration in [ticket 43](43-fnox-secret-delivery.md) preserves surviving-service credential references under pod042 without approving or activating their deployments. When this portfolio review retires a service, remove its associated fnox declarations and credential consumers too, after checking whether another retained service shares them. Do not retain dormant credential entries or delete 1Password items as an incidental cleanup. TrueNAS administration/SSH and Storj-node-only references retire with those already-retired consumers; Storj rclone/Uplink client access remains distinct.

## Resolution

Reviewed 2026-09-07 against the last TrueNAS and pod042 playbooks, all retained Compose sources, preserved application state, current fnox declarations, and the accepted private-bridge ingress contract. Restore eleven independently reconciled Compose projects: ingress, Plex, torrent, Arr applications, AnyPod, Ghost, CLI Proxy API, Homepage, iSponsorBlockTV, Scrypted, and the PON monitor. The live platform project already supersedes the old standalone Watchtower stack.

Ingress owns Caddy, cloudflared, and DDClient. They share one operational boundary but no artificial Compose startup dependency: Caddy terminates trusted local TLS and receives HTTP from cloudflared after Cloudflare's public TLS termination, cloudflared owns the outbound tunnel, and DDClient maintains the home-IP bypass. Public application projects join the explicitly shared ingress network under stable service names. Only Caddy publishes 80/443; Plex retains direct 32400. Homepage deploys last because it describes the rest of the portfolio. Torrent and Arr remain separate projects but restore in that order because Arr consumes qBittorrent.

Scrypted remains the dedicated UniFi Protect to Apple Home bridge. The earlier retirement had no recorded product rationale and contradicted the preserved live state: its database was active through cutover and contains the UniFi Protect, HomeKit, and prebuffer plugins plus the paired cameras. Home Assistant may independently consume Protect for automations, but does not replace Scrypted's camera-focused HomeKit Secure Video path. Scrypted is an explicit host-network exception because HomeKit discovery and media do not fit behind Caddy; Bunker joins the scoped UniFi mDNS domain and Lunar Tear home hubs receive routed access to fixed Scrypted accessory ports.

Retain the existing application identities and data under `/mnt/black-box/docker/<project>` and shared content under `/mnt/ark/media`, repathing every old `capacity` and `performance` reference rather than retaining compatibility links. Preserve `/watch` inside the torrent and Arr containers so their application-managed paths continue to address the same shared media tree without a second in-container migration. Images with `PUID`/`PGID` support use `1000:3000`; image-defined identities remain explicit per project, and ownership changes apply only to consumed persistent paths. Environment files carry interpolation secrets consistently. Compose owns internal dependencies, health ordering, private networks, and service lifecycle; native mise owns each project declaration and serial host convergence.

Do not resurrect undeclared data merely because it survived consolidation. Scrypted is the only correction to the accepted roster. Storj node, OpenClaw, Frigate, the old Home Assistant containers and HAOS VM, Arcane, PrivateBin, Obsidian LiveSync, Pinchflat, Podsync, SSH containers, Scrypted's former Frigate dependency, and superseded updater/repair sidecars remain retired or quarantined. The future Home Assistant VM remains separate work.
