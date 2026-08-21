# UDMP network audit

Research for [ticket 14](../tickets/14-udmp-network-audit.md). Every fact below was read live from the UniFi Dream Machine Pro on 2026-08-19 — controller API (`https://192.168.1.1/proxy/network/...`, local-admin session) plus read-only shell over `ssh udmp`. Nothing was written to the router. Two supporting reads were taken from the TrueNAS host (`docker network inspect`, Plex `Preferences.xml`) to resolve container identity behind the MAC addresses the firewall rules name; both read-only.

Device: `Dream-Machine-Pro`, UniFi OS 5.1.30, kernel 4.19.152-ui-alpine, WAN `eth9` = 108.207.130.230/23.

Observed facts are stated plainly. Where I reason past the data I say **Inference**.

## Headline

Three findings decide ticket 13's shape.

**The current "reverse proxy" is the UDMP itself.** Caddy serves exactly one static site (`thurstons.house` → `/srv`); every other service is reached at its own container IP on its own VLAN, resolved by a UDMP local-DNS record. So today's per-service access control *is* the VLAN membership. Moving to one caddy is not a refinement of the current model — it replaces it wholesale.

**Half the firewall rules are container plumbing that dissolves on contact with the new model.** Of the 23 custom policies, nine name a Docker macvlan MAC as source. Seven of those nine are container-to-same-host traffic that only left the machine because macvlan forced it out onto the wire and back. They vanish. Two survive as host-to-host and get *coarser*, which is the honest cost of the change.

**The only thing bridges genuinely cannot express is blast-radius containment for the internet-published set.** The `External` VLAN (192.168.5.0/24, zone "Soft External") has no SSID, no DHCP client, no human device — it exists solely so that seerr, ghost, anypod, cli-proxy-api, and cloudflared sit in a zone that cannot reach `Internal` or `Personal`. `remote_ip` matchers control who reaches a service; they say nothing about where a compromised service may go. That is the one decision ticket 13 has to make deliberately rather than inherit.

## Current-state map

### Networks

Live, from `GET /proxy/network/api/s/default/rest/networkconf` and `ip -br a` on the router:

| Name | VLAN | Subnet | Router iface | DHCP pool | mDNS | Zone |
| --- | --- | --- | --- | --- | --- | --- |
| Default | untagged | 192.168.1.0/24 | `br0` | .6–.224 | on | Internal |
| IoT | 2 | 192.168.3.0/24 | `br2` | .6–.224 | on | IoT |
| External | 3 | 192.168.5.0/24 | `br3` | .6–.224 | on | Soft External |
| Personal | 4 | 192.168.6.0/24 | `br4` | .6–.224 | on | Personal |
| WireGuard Server | — | 192.168.4.0/24 | `wgsrv1` | .6–.254 | — | Vpn |
| Thurston's House (Identity VPN) | — | 10.100.0.0/16 | `uid-wg` | — | — | Vpn |
| Mullvad (WAN client) | — | 10.64.104.181/32 | `wgclt1` | — | — | External |

Every DHCP pool stops at `.224`, and the NAS's macvlan `iprange` on each network is `.224/27` (`ansible/playbooks/truenas.yml`). The carve-out is deliberate and it holds: no DHCP lease has ever collided with a container.

This maps to `lan:` in `ansible/inventory/targets/group_vars/truenas.yml` exactly as documented — `trusted` = Default, `iot` = IoT, `external` = External, `personal` = Personal. One correction to the comment in that file: `trusted`'s macvlan `iprange` is `192.168.1.224/27` in the playbook, not "host network".

Wi-Fi (`rest/wlanconf`) — note which network has no SSID:

| SSID | Network |
| --- | --- |
| Taskmaster | Default |
| Phantom Zone | Default |
| Fortress of Solitude | IoT |
| Ellery Queen | Personal |

**`External` has no SSID and no wired port profile.** The only port profile besides "All" is `NAS` (`rest/portconf`: `forward: all`, native network Default) — i.e. the NAS uplink is a trunk carrying every VLAN tagged, with Default untagged. That trunk exists for exactly one reason: to let `br0.2/3/4` on the NAS parent the three macvlan networks.

Static route: `192.168.11.0/24` via WAN interface, named `WAS-110` — the fiber bypass module's management subnet ([ticket 16](../tickets/16-fiber-bypass-stability.md)).

### Zones

The router is on the zone-based firewall (`rest/firewallrule` is empty; all policy lives in `/v2/api/site/default/firewall-policies`, 166 policies, 143 predefined + 23 custom). Zone membership:

- **Internal** — Default network only.
- **IoT** — IoT network only.
- **Soft External** — External network only.
- **Personal** — Personal network only.
- **External** — the two WAN networks + the Mullvad WAN client.
- **Vpn** — WireGuard server + Identity VPN.
- **Gateway** — the router itself. **Hotspot**, **Dmz** — defined, empty, unused.

Default matrix (predefined `Block All Traffic` at index 2147483647, overridden by custom policies at index 10000):

- `Internal → *` allowed (three custom `Allow All Traffic` policies to IoT / Soft External / Personal, hits 981990 / 22895 / 1015781).
- Everything else inbound to a LAN zone is blocked unless a custom policy says otherwise. Live proof of enforcement: `Block All Traffic: Personal → Internal` has 33690 hits, `IoT → Internal` 149 hits.
- All LAN zones → `Gateway` and → `External` (WAN) allowed. `External → Gateway` blocked except the WAN plumbing set (WireGuard, DHCPv6, RA/NS/NA, Identity VPN).

So the model is: **Default is the trusted tier and reaches everything; every other tier is quarantined from Default and from each other, with hand-cut holes.**

### Devices per tier

From `rest/user` (209 known clients) reconciled against `stat/sta` (62 active). Rounded to what matters for ticket 13.

**Default / Internal — 192.168.1.0/24.** The house's trusted tier, and also a junk drawer.

- Infrastructure: UDMP `.1`, honeypot `.2`, TrueNAS `.68` (`Truenas Host br0`, MAC `36:79:cd:6f:26:05`), HAOS VM `.89` (`00:a0:98:70:3e:8b`), openclaw `.90` (`00:a0:98:26:3f:c2`), pod042 `.94`, glkvm `.34`, five UniFi APs (`bedroom .26`, `closet .39`, `garage .81`, `dining .82`, `study .171`), Living Room Camera `.31`.
- Personal computers and phones: Macs `.92`/`.156`, `ThurstonsiPhone .56`, watches.
- Media and smart-home that never got moved: Apple TV 4K `.91`, HomePods `.24`/`.45`, Google Home Max `.240`, Google Nest Hub `.79`, Remote Two `.105` + dock `.145`, Denon receiver `.125`, three Nest thermostats `.86`/`.155`/`.221`.

**IoT — 192.168.3.0/24.** ~25 devices, all on `Fortress of Solitude` or wired: Canon printer `.51` (`printer.thurstons.house`), Lutron Caseta hub `.41`, Bond Bridge `.47`, Elgato Key Light `.48`, LG C9 TV `.61`, washer `.216`/dryer `.65`, Whirlpool oven `.98`, Feeder Robot `.117`, Litter Robot `.211`, Lockly lock `.126`, ratgdo `.150`, Eight Sleep `.183`, Roomba `.185`, Sense monitor `.186`, Tesla Wall Connector `.191`, Flo by Moen `.206`, Fi collar hub `.222`, an APC UPS `.182`, two TRMNL displays.

**Soft External — 192.168.5.0/24.** Docker macvlan only. `docker network inspect external` on the NAS, live:

```
cloudflared          192.168.5.225
seerr                192.168.5.227
anypod               192.168.5.231
bgutil-pot-provider  192.168.5.232
ghost                192.168.5.233
ghost_mysql          192.168.5.234
cli-proxy-api        192.168.5.235
```

**Personal — 192.168.6.0/24.** Humans plus the arr stack.

- People/devices: Yanie's iPhone `.18`, MacBookAir `.68`, Pixels, iPads, watches, `Maggies-Lenovo-ThinkPad .203`, Google Chromecast `.165`, Xbox `.220`, PS5 Pro `.128`.
- Docker macvlan (`docker network inspect personal`, live): homepage `.225`, gluetun `.226`, flaresolverr `.228`, prowlarr `.229`, sonarr `.230`, radarr `.231`, scrypted `.232`, homepage-docker-socket-proxy `.234`, isponsorblocktv `.235`, newtarr `.237`, caddy `.239`.

**Both `trusted` and `iot` macvlan networks are empty.** `docker network inspect trusted` and `iot` return no containers. The `trusted` network has never had a member in the repo (no compose file references it), and the `iot` network's only historical member — frigate at `192.168.3.227` — no longer exists on the host. Two of the four macvlan networks are pure ceremony.

### Local DNS

The UDMP resolves service hostnames straight to container IPs. `static-dns` plus per-client `local_dns_record`, live:

```
thurstons.house           → 192.168.6.239  (caddy)
dash.thurstons.house      → 192.168.6.225  (homepage)
torrent.thurstons.house   → 192.168.6.226  (gluetun)
prowlarr.thurstons.house  → 192.168.6.229
sonarr.thurstons.house    → 192.168.6.230
radarr.thurstons.house    → 192.168.6.231
scrypted.thurstons.house  → 192.168.6.232
newtarr.thurstons.house   → 192.168.6.237
cli-proxy-api...house     → 192.168.5.235
truenas.thurstons.house   → 192.168.1.68
plex.direct               → 192.168.1.68
clawdbot-admin...house    → 192.168.1.90
kvm.thurstons.house       → 192.168.1.34
printer.thurstons.house   → 192.168.3.51
```

Stale entries still present: `frigate → 192.168.3.227`, `crabwalk → 192.168.6.238`, `arcane → 192.168.6.236`, `ha.thurstons.house.inside → 192.168.5.226`, `pikvm → 192.168.1.107`, two duplicate `remote`/`remotedock` pairs. None of those hosts exist.

DNS itself: `nextdns` on the router listening `localhost:53`, three `dnsmasq` instances serving the bridges, `mdns all` (`ansible/inventory/targets/group_vars/udmp.yml`).

### Firewall rules, and what each is actually protecting

All 23 custom policies, live. Hit counters are the controller's; `null` means the API reported no counter, which is weaker evidence than a zero but still consistent with "never matched."

**Zone-wide grants**

| Policy | Effect | Hits | What it protects |
| --- | --- | --- | --- |
| Allow All Traffic: Internal → IoT | full | 981990 | Nothing — it *un*-protects. Declares Default the trusted tier. |
| Allow All Traffic: Internal → Soft External | full | 22895 | Same. Lets a laptop on Default hit any container's web UI directly. |
| Allow All Traffic: Internal → Personal | full | 1015781 | Same. This is how sonarr/radarr/homepage are reached today. |

Everything below is a hole cut in the default-deny that applies to the other three tiers.

**Smart-home holes** (all retire with HAOS + scrypted)

| Policy | Src → Dst | Hits | What it protects |
| --- | --- | --- | --- |
| Allow MQTT Devices | IoT (any) → HA `192.168.1.89` :1883,8883 | 42411 | Lets IoT sensors publish to Home Assistant *and nothing else on Default*. The single most load-bearing IoT hole. |
| Google Devices => HomeAssistant | Personal, 4 MACs → HA | 375092 | Chromecast/Nest speakers call HA for media + voice. Named MACs so a compromised random Personal device can't. |
| Allow Matter Devices | IoT, 3 thermostat MACs → HA | null | Matter/Thread commissioning path to HA. |
| HA Voice => HA | IoT, `20:f8:3b:09:5b:fb` → HA | null | Voice satellite → HA. MAC absent from the client DB; dead. |
| HA => Home Devices | Internal, HA MAC → 8 IPs across 3 VLANs | null | HA reaching down into devices it controls. Redundant: Internal → * is already allowed. |
| HA -> IoT Devices | Internal, HA MAC → IoT (any) | null | Same redundancy. |
| Scrypted => Apple Home | Personal, `aa:83:cc:9f:fc:1e` → HomePods/AppleTV | null | HomeKit bridging. MAC is scrypted's pre-pinning random MAC; the live container is `02:42:c0:a8:06:e8`. **Dead rule.** |
| Frigate -> Scrypted | IoT `02:42:c0:a8:03:e3` → scrypted | null | Camera detection feed. Frigate no longer exists. **Dead rule.** |
| Allow Printer | Personal (any) → printer `192.168.3.51` | null | The one Personal → IoT hole: phones and laptops can print, and reach nothing else in IoT. Survives the rebuild unchanged; nothing to do with caddy. |

**Container holes** — the ones that matter for ticket 13

| Policy | Src → Dst | Hits | What it protects |
| --- | --- | --- | --- |
| Overseerr => Arr Apps | Soft External `192.168.5.227` (+ a stale MAC) → `.229/.230/.231/.237` on 7878, 8989, 9696 | 154253 | Seerr may drive the arr APIs and *only* those ports on *only* those four hosts. Without it Soft External → Personal is fully blocked. |
| Overseerr => Plex | Soft External `.227` → `192.168.1.68:32400` | 27910 | Seerr's Plex library sync. One host, one port, into the trusted tier. |
| Homepage -> Truenas | Personal `192.168.6.225` → `192.168.1.68` | null | Dashboard widgets scraping the NAS. A Personal → Internal hole for one source. |
| External SSH Access | Soft External `192.168.5.225` (cloudflared) → group `SSH Hosts` = `192.168.1.68, .89, .1, .90` | 7 | The `*-ssh.thurstons.house` tunnel ingresses. This is how `ssh udmp` works from off-network. Cloudflared reaches four boxes on the trusted tier and nothing else. |
| Crabwalk -> Moltbot | Personal `192.168.6.238` → openclaw `192.168.1.90` | null | Container → separate machine. Container is gone. **Dead rule.** |

Four of the twenty-three rules are provably dead (source MAC or container no longer exists), and several more can never match because the device moved tier: `Allow Matter Devices` names three thermostats in the **IoT** zone, but all three are live on **Default** (`192.168.1.86/.155/.221`); `Google Devices => HomeAssistant` names the Nest Hub in **Personal**, but it is live at `192.168.1.79`. That is the cruft [ticket 15](../tickets/15-udmp-declarative-rebuild.md) is aimed at, quantified.

### North–south traffic

Port forwards (`rest/portforward`, confirmed in `iptables-save -t nat`):

| Name | WAN | → | Note |
| --- | --- | --- | --- |
| plex | 32400 tcp+udp | 192.168.1.68:32400 | with hairpin MASQUERADE for `br0` sources |
| storj | 28967 tcp+udp | 192.168.1.68:28967 | retires with the node |
| xbox tcp | 80 | 192.168.6.220:80 | |
| xbox udp | 88,500,3544,4500 | 192.168.6.220 | |
| xbox udp/tcp | 53,3074 | 192.168.6.220 | |

**That is the entire inbound surface.** Three notes.

*The 20460 forward does not exist.* [Ticket 06](../tickets/06-plex-catalog-to-compose.md) records Plex remote access on manual external port 20460. Live, the forward is 32400→32400 and Plex's `Preferences.xml` has `ManualPortMappingMode="1"` with no `ManualPortMappingPort` key — i.e. the default 32400. `customConnections="http://192.168.1.68:32400"`. Ticket 06's resolution should be corrected: rebuild a **32400** forward, not 20460.

*Torrent peering has no forward.* qbittorrent's 57412 appears in the compose file and nowhere in the router's NAT table. Peering is inbound-via-Mullvad through gluetun's tunnel, so the WAN side of the UDMP never sees it. **Inference**, but a well-supported one: the compose puts qbittorrent in `network_mode: service:gluetun`, and gluetun is the only thing that could be receiving peers.

*`storj.thurstons.house` is not an exposure — it is an IP tracker.* The record is `proxied = false`, ddclient keeps it pointed at the WAN address, and `terraform/cloudflare/locals.tf` reads it back as `home_ip` to build the Cloudflare Access **"Home Network Bypass"** policy (`zero_trust.tf`). The only service ever bound behind it was the storj node on 28967. So ddclient's reprieve in ticket 05 is correct, but the reason is different from the one recorded: the record survives because Zero Trust policy depends on it, not because something is served on it. After storj retires, nothing listens on that name.

Everything else published is Cloudflare Tunnel, no inbound port at all: `seerr`, `anypod`, `blog`, `cli-proxy-api`, `openclaw`, plus four `*-ssh` hostnames (`terraform/cloudflare/locals.tf`).

### Multicast

- Avahi runs on the router as an **mDNS reflector across all four LAN bridges**. `/run/avahi-daemon.conf`, live: `allow-interfaces=br0,br2,br3,br4`, `[reflector] enable-reflector=yes`, no `reflect-filters`. Every `.local` announcement on any VLAN is republished onto the other three.
- Predefined `Allow mDNS: <zone> → Gateway` policies exist for all four LAN zones, hits ~1.96M each — the reflector is carrying real traffic continuously.
- `multicast_querier=1` and `multicast_snooping=1` on `br0/br2/br3/br4`, set by this repo's `multicast-querier.service` (`ansible/playbooks/udmp.yml`) and confirmed live in `/sys/devices/virtual/net/*/bridge/`. The playbook's stated reason is TREL reassembly timeouts for Thread/Matter.
- `igmp_snooping` is `false` on every network in the controller config, which is the UniFi-level setting; the kernel-level snooping the querier script depends on is on. **Inference**: the script exists precisely because the controller's own setting does not produce a querier.

## What the caddy model cannot express

The proposed model: bridges, no per-container LAN IPs, one caddy terminating HTTPS for every service, per-service access control via `remote_ip` matchers plus UDMP rules to the single bunker host. Here is what falls outside it, in descending order of how much it should worry ticket 13.

### 1. Blast-radius containment for the internet-published set

**What it is.** The `External` VLAN exists for one purpose: seerr, ghost, ghost_mysql, anypod, bgutil, cli-proxy-api, and cloudflared sit in a zone that is default-denied toward `Internal` and `Personal`, with two named exceptions (seerr→arr ports, seerr→plex:32400) and one for cloudflared (SSH to four hosts). These are the processes most likely to be compromised — they parse hostile input from the internet.

**Why caddy cannot cover it.** `remote_ip` is an *ingress* matcher. It decides who may talk to a service. Containment is about *egress* — where a compromised service may talk to. A caddy matcher is not in that path at all. Under bridges, every container's traffic leaves the bunker SNAT'd to the bunker's single host IP, so the router cannot tell ghost from sonarr from the host itself. A hole punched for one is a hole for all.

**Alternatives, in order of cost.**

1. *Accept it, and put the bunker in a restricted tier.* The published set has no inbound LAN exposure today either — it is all cloudflared, and cloudflared's own inbound is a tunnel. If the bunker as a whole lives in a tier that may reach the internet and almost nothing on the LAN, the containment moves from "per-container" to "per-host" and the loss is bounded. Docker's own inter-network isolation still separates the stacks from each other on the bridge side.
2. *Keep one macvlan attachment for the published set only.* Two macvlan networks instead of four, no change to the caddy model for everything else. This is the surgical escape hatch, and it costs the trunk port staying a trunk.
3. *A second runtime boundary* — the published stacks in their own LXC/VM with its own IP. Buys real separation without macvlan, at the cost of the substrate decision in ticket 05.

The counter-argument for option 1 is strong and worth putting to the user directly: the current separation buys little, because `Internal → Soft External` is fully open, so a compromise of anything on Default reaches the published containers anyway, and the trusted tier is where the NAS, HAOS, openclaw, the Macs, and the phones all live. The zone is a one-way wall with the valuables on the open side.

### 2. mDNS reflection and multicast — never was caddy's business, and must be re-decided anyway

**What it is.** The router reflects mDNS unfiltered across all four LAN bridges, and this repo forces a multicast querier on all four for Thread/Matter. This is what makes AirPlay to HomePods on Default work from Personal, Chromecast discovery work, and AirPrint find the IoT-tier printer.

**Why caddy cannot cover it.** mDNS is UDP multicast to 224.0.0.251. There is no hostname, no TLS, no HTTP. It is a property of the L2 domain and the router's reflector.

**What actually changes.** Nothing *for containers*, because after HAOS and scrypted retire, no container needs to announce or discover on a client VLAN. Both of the historical cases were smart-home bridges (scrypted advertising HomeKit accessories, frigate discovering cameras) and both retire. Plex's GDM discovery already only works within the host's own VLAN and clients use `plex.direct`/32400 explicitly — no regression.

**The real note for ticket 13**: a container on a Docker bridge is structurally incapable of joining a VLAN's multicast domain. If any *future* workload needs to advertise itself over mDNS to a client VLAN, macvlan is the only answer within this architecture. Worth writing down as the standing rule rather than rediscovering it. And the reflector's current configuration — unfiltered, all four bridges, both directions — is itself a segmentation hole that a whole-house redesign should reconsider: it lets any VLAN enumerate every other VLAN's services by name.

### 3. Non-HTTP services that must keep host ports

Caddy is an HTTP(S) gateway. These are not HTTP, or are HTTP with a protocol wrapper caddy would break:

- **Plex 32400** — host port + WAN forward, unchanged. `plex.direct` certificate pinning and the plex.tv direct-connection handshake mean this cannot live behind a general-purpose proxy for the remote-access path. Keep it a host port. (The *local* path could go through caddy, but there is no reason to split it.)
- **Torrent peering (gluetun)** — its own network namespace and its own tunnel. Untouched by the caddy question, and the reason gluetun keeps a distinct network identity regardless of what the rest of the stack does.
- **SSH 22 / 22222** — served by cloudflared as `ssh://` tunnel ingress, not HTTP.
- **MQTT 1883/8883** — retires with HAOS. The rule carrying 42411 hits goes away with it.
- **Printer (IPP/AirPrint), Xbox/PS5 NAT, Denon, Chromecast** — device-to-device, never involved caddy, unaffected.
- **isponsorblocktv** — **Inference, but confirmed negatively.** No firewall rule names its MAC (`02:42:c0:a8:06:eb`), it sits in Personal, and Personal → Internal is default-denied with 33690 blocked hits. The Apple TV it targets is at `192.168.1.91`, on Default. Therefore it cannot be reaching the TV over the LAN today; its configured `screen_id` means it drives the TV through YouTube's cloud lounge API. It needs outbound internet and nothing else. **Free to move to a bridge.** Worth a five-minute confirmation before the cutover, since a local-discovery mode does exist in that project.

### 4. Firewall semantics that exist only because containers had their own IPs

Nine custom policies name a Docker macvlan MAC. Their fate:

**Dissolve entirely — both endpoints become the same host.**

- `Overseerr => Arr Apps` (154253 hits) — seerr and the four arr apps all land on the bunker. Container-to-container over a Docker bridge; the router never sees it. Replace with Docker network membership.
- `Overseerr => Plex` (27910 hits) — same host once Plex is a compose stack on the bunker.
- `Homepage -> Truenas` — homepage's target *is* the bunker.
- `Scrypted => Apple Home`, `Frigate -> Scrypted` — already dead, and both services retire.

**Survive but get coarser — and this is the one real regression.**

- `External SSH Access` — cloudflared → `192.168.1.68, .89, .1, .90`. Two of those (`.1` the router, `.90` openclaw) stay separate machines. The rule becomes `bunker-host → {udmp, openclaw}`, which means *every* container on the bunker inherits SSH reach to the router and openclaw, not just cloudflared.
- `Crabwalk -> Moltbot` — same shape (container → openclaw), currently dead, but it is the pattern that will recur.

**The general statement.** Under macvlan, the router could distinguish 18 principals on the NAS. Under bridges it can distinguish one. Any rule of the form "only *this* container may reach *that* off-host thing" degrades to "the bunker may reach that thing." There is no caddy feature that recovers this, because caddy is not in the path of a container's outbound connection.

**Alternatives.** (a) Accept: the surviving cases are two, both toward machines under the same administration. (b) Move the target onto the bunker — openclaw's agent platform is already slated to land there ([ticket 07](../tickets/07-agent-platform-on-proxmox.md)), which would delete the problem rather than solve it. (c) Per-container egress control on the host itself — docker network scoping plus host nftables keyed on the bridge subnet. This is the technically correct answer and it moves enforcement from the UDMP into the bunker's own config, which the repo can reconcile. Worth raising in ticket 13 as the enforcement-split question it already lists.

### 5. Things the audit found that are not about caddy at all, but belong to ticket 13

- **Default is not a tier, it is a junk drawer.** The trusted 192.168.1.0/24 holds the router, the NAS, HAOS, openclaw, pod042, five APs, a KVM, a camera — *and* Apple TV, three HomePods, a Google Home Max, a Nest Hub, three Nest thermostats, a Denon receiver, two Macs, an iPhone, and assorted watches. `Internal → *` is fully open. Any of those consumer devices is a pivot into every other tier. This, not the container VLANs, is the segmentation problem in the house.
- **Two of four macvlan networks are empty** (`trusted`, `iot`) and two of four VLANs would be empty of humans without containers (`External` entirely). The tier inventory ticket 13 wants to design is smaller than the current one, not larger.
- **The NAS trunk port exists solely to serve macvlan.** Drop macvlan and the `NAS` port profile becomes an access port on one VLAN — a real simplification for the physical rebuild.
- **Rule cruft is measurable**: 4 provably dead rules, 3 more that can never match because their devices changed tier, 6 stale local-DNS records, 2 duplicate `remote`/`remotedock` entries. Hard evidence for ticket 15's wipe-and-redeclare.

## Gaps

- Hit counters returned `null` rather than `0` for several policies. `null` is consistent with "never matched" but the controller does not distinguish that from "not counted," so I treated only positive counters as evidence of live use.
- `rest/user` `last_ip` is stale for many clients (it disagrees with `stat/sta` for the Nest Hub, the thermostats, and most IoT devices). Device-tier statements above are taken from `stat/sta` where the client is currently online, from `rest/user` otherwise, and I flagged the two cases where the disagreement matters to a firewall rule.
- The 62-entry active-client list does not include every running container (homepage, caddy, prowlarr and others were absent from `stat/sta` despite running). macvlan containers only appear when they ARP. Container inventory above therefore comes from `docker network inspect` on the NAS, which is authoritative.
- isponsorblocktv's transport is inferred, not observed. A packet capture or a container log check would settle it.
