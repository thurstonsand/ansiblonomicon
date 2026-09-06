# UniFi provider fork

## Status

Accepted

## Decision Summary

OpenTofu remains the sole writer of UniFi Network application configuration. A permanent `thurstonsand/terraform-provider-unifi` fork adds typed resources and attributes missing upstream, publishes portable multi-platform binaries through GitHub Releases, and is installed by ansiblonomicon into OpenTofu's implied filesystem mirror without registering the provider with OpenTofu.

## Problem Statement / Background

At the start of this work, the rebuilt UDM Pro was mostly declared through `ubiquiti-community/unifi` 0.55.0, but recurring controller state still depended on dashboard actions. The missing state includes the Gateway mDNS Proxy policy, WAN identity and physical bindings, and safe adoption of some hardware. Native mise bootstrap cannot fill this gap: it owns host files and services, and its dry-run does not execute project tasks. A separate Python writer would duplicate OpenTofu's state, planning, locking, sensitivity, import, and lifecycle behavior while racing the existing provider.

The provider's current main branch already uses Terraform Plugin Framework throughout. Its `go-unifi` SDK models most missing controller fields, and the existing resources already implement the read-modify-write behavior needed to preserve controller-owned fields. Extending that provider keeps one writer and one plan.

## Goals

- Eliminate recurring UniFi dashboard configuration after the initial trust ceremony.
- Keep one typed OpenTofu owner for every writable controller field.
- Install the fork reproducibly on macOS and Linux, on ARM64 and AMD64.
- Preserve secrets in 1Password and access-controlled remote state, never Git or diagnostic output.
- Make a factory reconstruction require only the initial trust ceremony and physical operations.
- Periodically rebase onto upstream and delete fork code when upstream gains equivalent behavior.

## Non-Goals

- Reconcile the WAS-110 firmware or identity through the UniFi provider.
- Automate cloud login or multi-factor authentication.
- Permit any automated Power Distribution Pro relay write.
- Submit the fork's changes upstream.
- Build a generic API or reconciliation framework beside OpenTofu.

## Exposed Shape

### Provider dependency

`terraform/unifi/versions.tf` requires an exact `github.com/thurstonsand/unifi` version. The hostname identifies the fork but is not expected to implement the provider registry protocol.

`mise run unifi:provider:install` reads a committed release manifest, selects the current OS and architecture, downloads the matching GitHub Release archive, verifies its committed SHA-256 digest, and installs the executable under OpenTofu's implied filesystem mirror at `~/.terraform.d/plugins/github.com/thurstonsand/unifi/<version>/<os>_<arch>/`.

`mise run unifi:init` depends on that installation. Normal `tofu init`, plan, and apply behavior follows after installation. The shared R2 backend enables OpenTofu's native S3 lockfile; an isolated conditional-write test confirmed R2 rejects a competing lock acquisition.

### Controller declarations

HCL remains the only desired-state language. New provider fields extend existing resources rather than creating partially overlapping writers:

- `unifi_setting.mdns` owns global mDNS mode, network scope, and predefined/custom services.
- `unifi_wan` owns each WAN's logical role, failover priority, and sensitive MAC override.
- `unifi_device.ethernet_override` owns the declared physical interface-to-network-group assignments while preserving undeclared interfaces.
- `unifi_static_route` owns the WAS-110 LCT interface route.
- `unifi_setting.mgmt` owns Network-device automatic upgrades.
- `unifi_device` owns safe switch and AP adoption by stable hardware identity.

The provider must read the latest complete controller object, replace only declared fields or selected collection members, write it, and re-read it. Duplicate or ambiguous identities fail rather than choosing one.

### Behavioral verification

`mise run unifi:smoke` checks behavior outside Terraform's configuration model: direct Internet state without revealing the public address, 10 Gb/s link operation, LCT reachability, linked-profile NextDNS resolution, and scoped discovery from YoRHa. Native UDM reconciliation, not NextDNS's privacy-preserving diagnostic token, owns and verifies the exact profile ID. The smoke command performs no writes.

### Recovery workflow

A later `mise run unifi:bootstrap` wizard sequences the initial trust ceremony, targeted OpenTofu stages, physical reset prompts, adoption, native mise bootstrap, WAN cutover, and smoke checks. It invokes the sole writers rather than calling controller write APIs itself.

## Call Stacks and Data Flow

```txt
mise run unifi:init
  -> unifi:provider:install
    -> release manifest
    -> GitHub Release archive
    -> SHA-256 verification
    -> implied filesystem mirror
  -> tofu init
```

```txt
HCL desired state
  -> OpenTofu plan/state lock
  -> thurstonsand/unifi provider
  -> go-unifi SDK
  -> UniFi controller API
  -> provider re-read
  -> refreshed remote R2 state
```

```txt
mise run unifi:smoke
  -> local controller reads and external probes
  -> redacted named results
  -> zero or nonzero exit
```

A provider-source migration is a one-time state operation. The committed source address changes, an encrypted state snapshot is taken without plaintext storage, and `tofu state replace-provider` rewrites only provider addresses in shared R2 state. Resource IDs and remote objects do not change.

## Design Decisions

### 1. OpenTofu is the reconciliation framework

The fork extends the existing provider instead of introducing another mutation engine. This retains saved plans, remote locking, import, lifecycle, sensitive attributes, and removal semantics.

### 2. The fork is permanent but minimized

The fork is not an upstream waiting branch. Its single `release` branch stays rebased directly on `upstream/main`, and its rebase skill first removes changes made redundant upstream. Release notes record the exact upstream base commit.

### 3. GitHub Releases feed an implied filesystem mirror

A public registry submission is out of scope. GitHub alone does not implement the provider registry protocol, so ansiblonomicon installs verified release artifacts into OpenTofu's documented local mirror layout. This needs no per-machine CLI configuration and works on every released platform.

### 4. Controller configuration and runtime health remain distinct

Provider resources and data sources represent controller state. End-to-end network behavior remains a smoke test because a sleeping HomePod or transient upstream failure must not manufacture Terraform drift.

### 5. Infrastructure hardware identities may be committed

Stable switch and AP MAC addresses identify owned equipment and may appear in HCL, matching existing managed clients. The cloned ISP WAN MAC remains sensitive and enters through a 1Password-backed variable.

### 6. The PDU has no relay mutation path

The provider adopts and observes the PDU, but its resource schema exposes outlet state as computed-only and its SDK removes every `outlet_*` key at the final device-update boundary. HCL cannot express relay or cycle changes. Outlet names go with them: `name` lives inside `outlet_overrides`, so naming an outlet is a controller-side act, recorded here rather than declared.

A name-only merge modelled on `port_override` is not a safe substitute. `DeviceOutletOverrides` marks `relay_state` and `cycle_enabled` `omitempty`, so an outlet that is off round-trips through the struct with its key absent, and the controller's reading of an absent key cannot be probed safely on a PDU that powers the gateway. This is the failure class of #430. A write path would have to bypass the struct with raw JSON and refuse to invent entries; the cost is not worth a label.

The outlets are therefore asserted rather than declared. `unifi_device.power_distribution_pro` carries a `postcondition` failing the plan unless outlets 5 and 7 both report `relay_state = true`, and the `pdu_outlet_names` check warns, without blocking, when an expected outlet name is missing.

## Edge Cases & Failure Modes

- **Wrong provider artifact:** checksum verification fails before installation.
- **Unsupported platform:** installation fails and lists the released platform matrix.
- **Missing mirrored provider:** `unifi:init` installs it before OpenTofu performs discovery.
- **Controller normalizes a field:** import and refreshed plan must converge before any apply; otherwise the field remains unowned until the provider conversion is corrected.
- **Unknown fields share a PUT object:** the provider fetches and preserves them. Typed serialization must have fixture and live tests for empty/null collections.
- **WAN apply loses connectivity:** stop. Do not attempt an automatic rollback through the connection that disappeared.
- **Two WANs change together:** apply serially with a reviewed saved plan and verify connectivity after each stage.
- **Provider source migration fails:** restore the encrypted state snapshot and leave controller objects untouched.
- **A controller-affecting PDU update appears in a plan:** reject the plan; no relay or generic PDU write is acceptable. Terraform-only lifecycle flags may converge through the provider's no-request state path.
- **Controller update changes payloads:** require a refreshed clean plan and smoke canary before applying controller changes.

## Alternatives

### Python write reconciler

- **Status:** Rejected
- **Decision:** It would become a second provider without state identity, saved plans, shared locking, or complete lifecycle behavior.

### OpenTofu Registry publication

- **Status:** Rejected
- **Decision:** The user does not want to submit or register the fork with OpenTofu. GitHub Releases plus the implied mirror retain portability without that relationship.

### Local provider builds on every host

- **Status:** Rejected
- **Decision:** Requiring Go and a source build on laptops and the NAS is slower and gives each host another way to produce a different binary.

### Generic REST provider

- **Status:** Rejected
- **Decision:** UniFi's authentication, singleton settings, collection replacement, and private endpoint normalization require typed endpoint-specific behavior.

### Native mise bootstrap task as controller writer

- **Status:** Rejected
- **Decision:** Its dry-run omits tasks, it would place controller credentials on the UDM unnecessarily, and it would still create a second writer.

## Implementation Plan

- [x] Phase 0: Prove existing provider boundaries
  - Goal: Move already-supported state into OpenTofu and identify exact missing fields without speculative writes.
  - Files: `terraform/unifi/`, current-state documentation.
  - Work: Import the LCT route and site management setting; inspect mDNS, WAN, Ethernet override, device, and Integration API shapes; correct the false forced-speed claim.
  - Validation: Refreshed **No changes** plan and unchanged Internet/LCT behavior.

- [x] Phase 1: Deliver mDNS through the fork
  - Goal: Prove SDK change, provider resource, release artifact, portable installation, source migration, and live reconciliation end to end.
  - Files: both fork repositories; provider installer and OpenTofu declarations in ansiblonomicon.
  - Work: Add complete mDNS models and `unifi_setting.mdns`; add tests; create release workflow and maintenance skill; publish platform artifacts; install through mise; migrate provider source once; declare and import live mDNS.
  - Validation: Provider tests, checksum failure tests, installation smoke on macOS, clean live plan, and AirPlay/HomeKit discovery.

- [x] Phase 2: Own WAN configuration
  - Goal: Move logical and physical WAN state plus the sensitive clone into typed resources.
  - Files: fork WAN/device resources and `terraform/unifi/`.
  - Work: Add sensitive MAC override and Ethernet override schema/conversions; import WAN2 then WAN1; declare physical bindings; keep changes serial.
  - Validation: Zero-change imports followed by public lease, Internet, LCT, and 10 Gb/s full-duplex checks.
  - Progress: Both logical WAN records, priority/failover state, and the sensitive MAC override are imported and round-trip at **No changes**. Provider release `v0.56.0-ansiblonomicon.3` fixes the previously omitted WAN MAC wire encoding, redacts that value from validation and API errors, and makes removing the attribute clear the controller clone. No live WAN write was manufactured merely to exercise it. Release `v0.56.0-ansiblonomicon.4` adds partial `unifi_device.ethernet_override` ownership; the UDM now declares only `eth8`/WAN and `eth9`/WAN2 while preserving every other live interface entry and unmanaged field. The state-adoption apply contained only those already-matching blocks, the next refreshed plan reported **No changes**, and the eight-check smoke gate passed.

- [x] Phase 3: Make adoption recoverable
  - Goal: Let OpenTofu adopt expected switches and APs after their physical reset, and safely represent the PDU.
  - Files: fork device resource/tests and `terraform/unifi/ports.tf`.
  - Work: Declare stable identities and adoption; diagnose and fix PDU normalization; expose no relay writes.
  - Validation: No unexpected device update, clean plan, adopted/online inventory, critical PDU outlets still powered.
  - Progress: Provider release `v0.56.0-ansiblonomicon.5` makes outlet attributes computed-only, removes their model-to-request conversion, and normalizes block-less device state to empty collections so imported devices no longer plan perpetual updates. The runtime assertions decision 6 anticipated now exist: a `postcondition` gating outlets 5 and 7, and a warning-only name check, both verified live by inverting the expected name and watching the warning fire. The SDK excludes every `outlet_*` key from the final device patch, including the separate port action path. OpenTofu imported the Power Distribution Pro without a controller write; the only follow-up change set `forget_on_destroy = false` through a tested state-only path that performs no controller request. The refreshed plan reports **No changes**, all 20 observed outlets remain powered, and the eight-check smoke gate passes.

- [ ] Phase 4: Finish operator workflow
  - Goal: Reduce reconstruction to the initial trust ceremony and physical actions.
  - Files: mise tasks, smoke tests, recovery wizard, and current-state documentation.
  - Work: Add redacted end-to-end smoke checks; sequence targeted applies and physical prompts; remove superseded dashboard steps; document fork release maintenance.
  - Validation: Paper recovery drill, live no-op reconcile, smoke pass, and portable provider artifact verification for every target platform.
  - Progress: The redacted live smoke command passes all eight WAN, LCT, NextDNS, link, and mDNS checks. Recovery sequencing remains.
