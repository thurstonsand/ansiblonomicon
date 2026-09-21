# Desktop tools capability

This capability owns small, mutable desktop application files as regular copies. Both registered Macs receive Go's local-only telemetry mode. The personal Mac additionally receives LinearMouse, NextDNS, mactop, herdr, and eightctl configuration; work neither resolves the eightctl credentials nor touches those personal paths. The NextDNS file is configuration text only: this capability does not activate DNS or update its addresses.

Run `mise desktop-tools` or `mise laptop -t desktop-tools`. Add `--check` for a nonmutating preview. Preview uses non-secret eightctl placeholders, so it can report differences even when real values are converged. Apply on the personal Mac fetches only `EIGHTCTL_EMAIL` and `EIGHTCTL_PASSWORD`. See the [rollout ledger](../../../docs/operations/mise-migration-cleanup.md) for host verification.
