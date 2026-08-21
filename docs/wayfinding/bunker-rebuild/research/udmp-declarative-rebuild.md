# UDMP declarative rebuild

Research for [ticket 15](../tickets/15-udmp-declarative-rebuild.md). This is a read-only investigation. The live baseline remains the [UDMP network audit](udmp-network-audit.md); controller and shell queries made here did not write configuration.

## Verdict

**A clean, mostly declarative reconstruction is practical, but not a literal factory-to-final one-command restore.** Put controller objects with a lifecycle in `terraform/unifi/`, using OpenTofu and the active `ubiquiti-community/unifi` provider. Keep `ansible/playbooks/udmp.yml` for the unsupported UniFi OS layer only: NextDNS and, if the post-rebuild test still needs it, the multicast-querier. This follows the repository rule that Terraform owns lifecycle while Ansible reconciles hosts.

The provider can own the six target networks and their DHCP/VLAN details, zone-based firewall zones and policies, address/port objects, SSIDs, reservations and client names, local DNS, port profiles, the `WAS-110` static route, port forwards, and IPS/honeypot settings. It cannot be trusted to express the required **custom, three-network mDNS scope**: its per-network mDNS field is not the custom proxy policy, and its own documentation reports UniFi OS gateways can ignore it. That, console bootstrap, ISP/bypass setup, and physical downstream-device adoption remain explicit manual runbook steps. The official Integration API is becoming useful, but Network 9.1's published contract is almost entirely read-only and cannot be the reconstruction substrate.

The reset is worth doing because it avoids importing quantified cruft — 23 custom policies, four provably dead rules, three impossible matches, six stale local DNS records, and two empty macvlan networks — and because it avoids the *legacy-to-zone* conversion entirely. It is **not evidence that every zone/OON bug disappears**. Ubiquiti documents conversion as a conservative translation of old rules which deliberately creates redundant policies; a fresh configuration has no conversion to fail, but no vendor source promises that a fresh controller makes zone-policy creation defect-free.

Do **not** reset the production router before the move. Once AT&T has installed and proven the new connection, use the move's acceptable downtime to bring up a fresh console and a wired recovery LAN, recreate the WAN/bypass prerequisites (including the `WAS-110` route), then apply the declared controller state. The old backup is rollback/reference material only; restoring it reinstates the state this ticket is removing.

## Live facts that constrain the rebuild

The UDM Pro reports UniFi OS 5.1.30. Its local Network application's live Integration OpenAPI document reports **Network 10.5.67** (`http://127.0.0.1:8080/api-docs/integration.json`, read locally over the router's read-only SSH shell on 2026-08-19). The ticket was framed around Network 9.x because zone firewalling arrived in Network 9.0. The execution ticket must pin the tested controller/provider pair rather than assume the version at reset time.

The target is already decided by [ticket 13](../tickets/13-vlan-security-redesign.md): `infra`, `admin`, `household`, `discovery`, `appliances`, and `VPN`; a single Bunker access port in `infra`; Docker bridges rather than a NAS trunk/macvlan; wildcard local DNS to Bunker; zone policy for L3; and mDNS only between `admin`/`household` and `discovery`.

The following live requirements are cutover-critical:

- `WAS-110`: static route `192.168.11.0/24` through WAN. It is the management path to the XGS-PON stick at `192.168.11.1`. Treat it as an early Terraform declaration and a runbook verification, not a convenience setting.
- Plex: retain the one WAN forward, **32400 TCP+UDP → Bunker:32400**. The audit proved that the historical 20460 note was wrong. Retire the Storj 28967 forward; retain Xbox forwards only after the console's final `discovery` reservation is known.
- `storj.thurstons.house` remains the Cloudflare Access home-IP input until the Cloudflare state is changed. It is not a service forward, but deleting the DNS record is still a cross-stack break.
- WireGuard Server and Identity VPN carry into the `VPN` zone. Their server/peer identities and any resulting client configuration are not proven exportable by the chosen controller provider; preserve them separately before reset.
- `udmp-ssh` is currently reached by Cloudflare Tunnel through a narrowly-scoped controller policy. Re-establish tunnel reachability only after the Bunker and policy exist; retain local wired console access as recovery.

## Tooling landscape

### Providers: there is no single successor to `paultyng/unifi`

`paultyng/terraform-provider-unifi` is archived. Its own README names **three** published successors: `filipowm/unifi`, `ubiquiti-community/unifi`, and `akerl/unifi`; it explicitly says there is no single successor. The first two are active as of the research date:

- [`ubiquiti-community/unifi` v0.55.0](https://registry.terraform.io/providers/ubiquiti-community/unifi/latest/docs), published 2026-07-10, continues the v0.x lineage and has 50 registry versions. It has current explicit resources for networks, zone firewall policies/zones, port forwards, port profiles, static routes, WLANs, clients, DNS, firewall groups, and site settings.
- [`filipowm/unifi` v1.1.0](https://registry.terraform.io/providers/filipowm/unifi/latest/docs), published 2026-07-02, is a separately maintained v1 rewrite from the same ancestor. It advertises Network 9.x support, API-key authentication, zone resources/policy ordering, local DNS, port forwards/profiles, static routes, and a dedicated IPS resource. It has only three registry versions and its `unifi_client` documentation endpoint is missing at v1.1.0, so reservations/aliases are not a safe basis for this rebuild without a hardware spike.

**Recommended controller owner: `ubiquiti-community/unifi`, pinned to an exact tested version.** It covers every configuration object this ticket actually needs and documents import/drift semantics. This is a recommendation about the owner, not an assertion that the other fork is abandoned. `filipowm` is a viable alternate if its specific IPS/OON behavior tests better, but changing to it after writing state would be a schema/state migration. Do not mix both providers against the same controller objects.

Both providers operate mostly through the controller's longstanding local API rather than solely through Ubiquiti's new Integration API. Both accept a local username/password or a console API key; use a dedicated, least-privilege Local Access Only admin/API key from the secret system, never the human UI account. Both manage state, so an overlapping UI edit becomes Terraform drift and the next apply can overwrite it. That is desired for declared objects; it is a reason to put every intentional manual remainder in the runbook and not casually edit provider-owned UI fields.

### Capability matrix

`Yes` means the tool has a current documented resource/endpoint for it. `Partial` is an important boundary, not an invitation to assume the missing half works.

| Tool | Networks / VLANs | ZBF policies / zones | OON objects | NAT forwards | SSIDs | Fixed IP / alias | Local DNS | Port profiles | mDNS / IGMP | Threat / honeypot | Auth and UI boundary |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `ubiquiti-community/unifi` v0.55 | Yes | Yes | **Partial:** address/port firewall groups and policy object references; no proof that every newer OON traffic-matching object is modelled | Yes | Yes | Yes, `unifi_client` | Yes | Yes | **Partial:** per-network mDNS and IGMP fields. Its network docs warn UniFi OS gateways may ignore mDNS writes; no documented custom proxy scope/service filter | Yes: `unifi_setting.ips`, including categories, enabled networks, suppression, honeypot | Local admin/password or API key; optional cloud connector. UI edits drift/fight provider-owned state. |
| `filipowm/unifi` v1.1 | Yes | Yes, including zone-policy ordering | **Partial:** classic address/port groups; no proof for all OON object types | Yes | Yes | **Unproven:** v1.1 `unifi_client` docs are absent | Yes | Yes | **Partial:** network-level mDNS/IGMP fields, not proven custom proxy scope | Yes: `unifi_setting_ips`, including honeypots | Local admin/password or API key. UI edits likewise become state drift. |
| Official Network Integration API, **Network 9.1.120** | No | No | No | No | No | No | No | No | No | No | API key, local console or cloud connector. The published OpenAPI has sites/devices/clients, device restart/PoE actions, guest authorization, and hotspot vouchers — not configuration CRUD. |
| Official API on this controller, **Network 10.5.67** | Yes | Yes | **Partial:** traffic-matching lists plus firewall policies, but semantics must be tested | No | Yes | No | Yes, DNS policies | No | No gateway mDNS-proxy/IGMP-settings endpoint in the live spec | No | API key. The contract is version-specific; check the console's `integration.json` before implementation. |
| Ubiquiti-generated `ubiquiti.unifi_api` Ansible collection | Only what the installed official API exposes | Same | Same | Same | Same | Same | Same | Same | Same | Same | API key; a generic `path`/`method` caller, not resource modules or idempotence. On 9.1 it inherits the near-read-only limitation; on 10.5 it can call the supported subset but Ansible must implement GET/diff/error handling. |
| Community Ansible collections | No mature complete collection found. `domnikl.unifi_network` currently supplies DNS policy only. | No | No | No | No | No | DNS only | No | No | No | API key. It does not replace a provider or raw API role. |
| Raw local controller API / client | Broadest, including legacy controller-only endpoints where known | Yes, as demonstrated by the audit's `/v2/api/site/default/firewall-policies` reads | Potentially, but schema is private and release-sensitive | Yes | Yes | Yes | Yes | Yes | Legacy mDNS/IGMP settings can be called, but custom proxy scope must be validated against the UI/API payload | Yes | Local admin session or console API key. Same underlying data as the UI, but unsupported endpoints/schema changes mean a custom reconciler must own diffing and regression tests. |

The matrix distinguishes Ubiquiti's public contract from the API that existing providers use. The [official 9.1 OpenAPI](https://developer.ui.com/network/v9.1.120/openapi.json) proves the former was initially narrow. The 10.5 live spec proves that it has since grown to CRUD for networks, Wi-Fi broadcasts, firewall zones/policies, traffic matching lists, ACL rules, and DNS policies, but it still has no static route, port-forward, port-profile, reservation/alias, mDNS proxy, or IPS operation. Its generated [Ansible quick start](https://developer.ui.com/network/v9.1.120/quick_start.ansible) is a transport wrapper, not an idempotent collection.

[Art of WiFi's client](https://github.com/Art-of-WiFi/UniFi-API-client) is a maintained example of raw API tooling: it supports UniFi OS 5.x / Network 9.x and has a custom request escape hatch. It is useful as an implementation reference or a narrow stopgap, not as a claim that undocumented endpoints are stable enough to become this repo's primary abstraction.

### Why a Terraform tree fits better than an Ansible role

`terraform/cloudflare/` already gives the repo a precise precedent: OpenTofu owns objects with lifecycle, invoked by `poe tfp`/`tfa`; Ansible manages machine state. Networks, zones, firewall policies, DNS records, port profiles, reservations, and forwards are controller objects with create/read/update/delete identities and cross-object dependencies. They match Terraform state and import far better than an Ansible sequence of imperative `uri` requests.

An Ansible role would keep the `udmp` playbook aesthetically centralized, but no supported collection provides the resource model. A role would have to implement idempotency, lookup/adoption, rule ordering, partial-failure recovery, and API-version branches itself. That is a provider, only less visible. Use Ansible for the router's shell state, where it already speaks naturally through SSH/systemd.

The boundary should be:

- **OpenTofu `terraform/unifi/`:** site-owned controller lifecycle — networks/VLANs/DHCP, zones/policies and reusable groups, SSIDs, Bunker/clients reservations and aliases, wildcard local DNS, port profiles/assignment after device adoption, static routes, required forwards, and IPS/honeypot configuration once the final address is allocated.
- **Manual runbook:** console initial setup, API key bootstrap, AT&T/WAS-110 service identity and WAN validation, custom mDNS proxy service/VLAN scope, device factory resets/adoption, and any setting that the tested provider cannot round-trip.
- **Ansible `ansible/playbooks/udmp.yml`:** the NextDNS and optional querier OS services, after SSH has been re-enabled and the controller state is stable. It should not become a second controller writer.

A disposable-controller spike is mandatory before making the provider the recovery mechanism: create all six networks, zones/policies, a profile, a reservation, a wildcard record, route, forward, IPS/honeypot setting, and then run a clean plan. Test a UI edit only on an imported disposable object to establish the exact drift behavior. Do this wired to the gateway; both provider READMEs warn that changing network configuration from the Wi-Fi being changed is self-defeating.

## Factory reset and reconstruction

### What a reset does and does not prove

Ubiquiti describes factory reset as returning a device to factory default and, for a managed downstream device, unmanaging it. Its backup/migration documentation says a device showing “Managed by Other” must be reset and re-adopted if restore/migration does not retain management. A new gateway cannot preserve the old controller's adoption relationship merely because the cable topology stayed in place.

The documented legacy-to-ZBF migration maps each old rule set to zone pairs and intentionally creates multiple/redundant policies to preserve behavior. A factory-fresh Network setup has no legacy rules to translate, so it removes the conversion code path that accumulated this controller's redundant policies. It does **not** establish the cause of the old “enable errors,” nor prove a controller release has no fresh-ZBF/OON defects. There is no primary-source report I could verify that a factory reset cures those errors. Treat the fresh ZBF build as a smoke-tested change, with the pre-reset backup as rollback, not a magic repair.

### Manual/non-declarable remainder

These must be explicitly handled outside the controller Terraform apply. Some may become declarable after the pinned-version spike, but they are not safe assumptions now.

1. **Console bootstrap:** physical reset, first-run UniFi OS setup, UI account/owner, local recovery administrator, management SSH enablement, and creating the least-privilege Integration API key. The API cannot bootstrap its own credential.
2. **New-house WAN and bypass:** let AT&T provision its new gateway/ONT first. The old service's WAS-110 identity must not be assumed valid at the new address. Configure/test WAN, the new gateway's required identity/MAC details, and the `192.168.11.0/24` `WAS-110` route before making the stick the only connection. Terraform can subsequently own the static route, but cannot recover internet if this first bootstrap is wrong.
3. **Physical device adoption:** switches/APs left adopted to the old controller may report Managed by Other. Factory-reset and re-adopt them as necessary. Their port-profile assignment comes only after successful adoption. The official API can read devices and restart/power-cycle them; it does not create/adopt them.
4. **mDNS proxy custom policy:** set the Gateway's Custom mode to reflect only the chosen services between `admin`, `household`, and `discovery`; keep `infra` and `appliances` out. Ubiquiti documents that Auto retransmits common mDNS across all VLANs, while Custom lets the operator select VLAN scope and services. Neither official API contract nor provider documentation establishes a convergent representation of that custom scope. Capture the resulting controller payload during the spike before considering a narrowly-owned raw-API resource.
5. **Controller/UI settings outside tested resource coverage:** console-wide UniFi OS preferences, external integrations, backups/notifications, device-specific radio/switch tuning, and any VPN server/peer detail that cannot round-trip through the pinned provider. Record each as either a provider import or a runbook checkbox — not an unowned UI memory test.
6. **Port-specific hardware and ISP values:** port speed/duplex needed by the XGS-PON stick, physical cabling, AP placement/PoE recovery, and AT&T gateway service identity. They are environment facts, not controller objects safely inferred from the old backup.

The built-in threat-management honeypot is **not inherently manual**: both candidate providers document an IPS/honeypot resource. It remains a post-network-spike item because its address must be an intentionally unused `infra` IP and it must be proven to round-trip on this UDM Pro before becoming recovery-critical.

### OS layer: NextDNS and multicast querier

The current playbook installs `/data/multicast-querier.sh`, `/etc/systemd/system/multicast-querier.service`, and `/data/nextdns.conf`; it only *configures* the existing `nextdns` service. Live read-only verification found both services enabled, the files present, and the current configuration still targets the old `br0 br2 br3 br4` topology.

`/data` plus `/etc` are commonly used persistence locations across UniFi OS firmware upgrades, but this is not a Ubiquiti support contract. The maintained [unifios-utils](https://github.com/johnstonjs/unifios-utils) project documents both as upgrade-persistent on UniFi OS and is tested on 5.1.x; firmware upgrades can still rebuild other root filesystem state. A **factory reset is different**: it returns the console to factory state, so assume both custom files, the enabled unit, and the NextDNS installation/configuration are gone. Re-run/rework Ansible after initial setup; do not rely on an old `/data` surviving the wipe.

That exposes a small execution prerequisite: the current `udmp.yml` cannot rebuild NextDNS from blank because it does not install the binary/unit. The execution ticket must turn NextDNS into a complete, idempotent OS role or document its one-time supported installation before `poe udmp` is called.

mDNS proxy and IGMP querying solve different problems. The former reflects discovery packets across L3 boundaries; an IGMP querier maintains multicast membership on an L2 segment when snooping is active. Ubiquiti's mDNS documentation gives no basis for believing scoped reflection replaces a querier. Conversely, the audit's only proof for the custom service is the historical Thread/Matter/TREL timeout on the old topology, where controller `igmp_snooping` was false while the script forced kernel snooping/querier on every bridge.

So the rebuilt model should **not blindly retain the old four-bridge service**. First configure scoped mDNS manually and use the controller's current IGMP-snooping settings on the `discovery` network (and any future HA/Thread segment); then test the actual Thread/Matter workload. Keep/redeclare a querier only on the required bridge(s) if that test fails. The new design retires HAOS and scrypted, so there is no current workload proving all six networks need it.

## Recommended sequence around the move

The three timing choices have materially different risks:

| Timing | Benefit | Cost / decision boundary |
| --- | --- | --- |
| **Before the move** | Finds reset/adoption surprises while the old WAN is known. | It risks losing the currently working house and XGS-PON recovery path before a physical move. Do only an isolated provider/fresh-config lab spike, not the production wipe. |
| **During the move, before new WAN is proven** | Downtime is already acceptable. | Couples two unknowns: new AT&T service/bypass identity and a virgin controller. This is the worst failure domain. |
| **After AT&T proves the new WAN, on move day or immediately after** | Has a known-good new service, physical access to downstream devices, wired recovery access, and acceptable downtime. | Requires a temporary minimal configuration before the full apply. **Recommended.** |

Run it in this order:

1. **Before transport:** take encrypted/current system and Network backups, export the audit inputs, capture the provider/API version, reservation/SSID/port inventory, VPN client material, current WAN/bypass values, and Cloudflare dependencies. Backups are rollback/reference only — do not restore controller configuration into the clean rebuild.
2. **Let AT&T complete the new service with its supplied gateway first.** Verify the new service type and the gateway identity required by the WAS-110 method. Keep the AT&T gateway as rollback while validating the bypass; ticket 16's thermal/stability work remains independent.
3. **Factory-reset the UDMP with a laptop cabled to a LAN port.** Complete minimum console setup, make a local recovery admin and API key, re-enable SSH, bring up the new WAN/bypass, and re-create/verify `WAS-110` `192.168.11.0/24` via WAN. Confirm internet, stick management, and wired console access before changing LAN topology.
4. **Adopt the physical switch/AP estate.** Reset devices that remain owned by the old controller. Keep a temporary wired recovery port/profile until adoption and management are stable.
5. **Apply `terraform/unifi` in dependency order:** base networks/DHCP → zones/default-deny policies → static route and IPS/honeypot → profiles/assignments and SSIDs → reservations/aliases/DNS → required forwards → custom mDNS UI configuration. The Bunker gets one `infra` access port. Validate every zone direction from wired test clients before moving all household devices.
6. **Restore OS-layer declarative state:** make NextDNS installation complete, then run the `udmp` playbook. Test mDNS and Matter/Thread before deciding whether the narrow querier service returns. Reapply/verify after every firmware update until its persistence behavior is proven on this hardware.
7. **Prove recovery:** run a clean OpenTofu plan; test DNS wildcard, Plex remote access, Xbox only if retained, VPN, each zone's intended denied/allowed paths, scoped discovery, stick management, and Cloudflare Access home-IP behavior. Take a post-rebuild backup and keep the rollback capture until these pass.

## Open risks

- **Provider/controller drift:** neither community provider is Ubiquiti-supported. Pin versions and prove CRUD/import/plan on the UDM Pro's exact Network release before declaring it recovery-critical.
- **mDNS custom scope:** it is security-significant and absent from the documented convergent provider/API surface. A raw API resource is possible only after capturing a stable payload across a controller update; manual UI/runbook is safer today.
- **Adoption:** every AP/switch may need physical factory reset. Schedule it as a physical-access operation, not an automated expectation.
- **WAN/bypass:** the `WAS-110` route and new AT&T identity are availability-critical. Do not make the bypass the only recovery path until its new-address behavior and thermal stability have been verified.
- **ZBF/OON:** a fresh build avoids migration, not software defects. Create a minimal policy suite first, then run an allow/deny test matrix before full device migration.
- **OS persistence:** firmware persistence is community-documented, factory-reset persistence is not a reasonable assumption. The current NextDNS playbook is incomplete for a blank appliance.
- **Rule ordering:** policy order can affect matching. The community provider documents controller-assigned ordering in its ZBF policy resource; test final ordering and avoid untracked UI reorders.

## Primary sources

- [paultyng provider archive and successor statement](https://github.com/paultyng/terraform-provider-unifi)
- [`ubiquiti-community/unifi` provider and resources](https://registry.terraform.io/providers/ubiquiti-community/unifi/latest/docs)
- [`filipowm/unifi` provider and resources](https://registry.terraform.io/providers/filipowm/unifi/latest/docs)
- [Ubiquiti official Network 9.1.120 OpenAPI](https://developer.ui.com/network/v9.1.120/openapi.json) and [generated Ansible guide](https://developer.ui.com/network/v9.1.120/quick_start.ansible)
- [Ubiquiti: Getting Started with the Official UniFi API](https://help.ui.com/hc/en-us/articles/30076656117655-Getting-Started-with-the-Official-UniFi-API)
- [Ubiquiti: Zone-Based Firewalls](https://help.ui.com/hc/en-us/articles/115003173168-Zone-Based-Firewalls-in-UniFi) and [migration behavior](https://help.ui.com/hc/en-us/articles/28223082254743-Migrating-to-Zone-Based-Firewalls-in-UniFi)
- [Ubiquiti: mDNS Proxy](https://help.ui.com/hc/en-us/articles/12648701398807-UniFi-Gateway-Multicast-DNS)
- [Ubiquiti: factory reset](https://help.ui.com/hc/en-us/articles/205143490-How-to-Reset-UniFi-Devices-to-Factory-Defaults) and [backups/migration/re-adoption](https://help.ui.com/hc/en-us/articles/360008976393-Backups-and-Migration-in-UniFi)
- [Art of WiFi raw controller API client](https://github.com/Art-of-WiFi/UniFi-API-client)
- [unifios-utils persistence notes](https://github.com/johnstonjs/unifios-utils)
