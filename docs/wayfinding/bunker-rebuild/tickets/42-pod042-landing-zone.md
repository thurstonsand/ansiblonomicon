---
status: closed
type: task
blocked-by: [31]
claimed: 01a06a50-6c47-7603-aa39-e536fbce070a
---

# Implement the pod042 landing zone

## Question

Implement the accepted [native mise operating contract](../../../designs/24-pod042-native-mise-contract.md) far enough to permit erasing the TrueNAS boot SSD. Add the shared native target, guarded local/remote entrypoint, first-access workflow, and destructive Debian 13 VM gauntlet.

The landing zone owns manageability only: `thurstonsand`, passwordless sudo, key-only SSH, the system mise binary, required base packages, and `/home/thurstonsand/code/ansiblonomicon`. It must survive reboot and produce equivalent clean remote and local reconciliation. Do not import, rename, or alter any real ZFS pool, and never invoke the old Ansible playbook on the fresh host.

Close only after the VM has been destroyed and recreated once and the full landing-zone proof has passed again.

## Resolution

Closed 2026-09-05. The native target now owns the serial base landing zone and the minimum ZFS package/service capability. `mise pod042 [capability]` selects a shared local or remote declaration, rejects the wrong hostname, preserves exact clean Git revisions, supports an explicit SSH agent for unattended recovery, and never invokes the retired Ansible playbook. The first-access bridge installed the existing NAS operator key, retained the generated console password in the `agent` vault, established passwordless sudo, disabled SSH password authentication, installed system mise, and cloned the public checkout.

The amd64 Debian 13 OrbStack VM was destroyed and recreated. A blank replacement reached the base target remotely, survived reboot, converged locally and remotely without changes, reported induced SSH drift, repaired the managed file, rejected a wrong hostname before staging, and propagated an OrbStack-specific SSH socket reload failure instead of continuing. Fifteen focused tests cover Git guards, transport selection, secret handling, and failure paths. The VM's socket-activated SSH service cannot reload like the real host, so the rig required stopping `ssh.socket` after the expected fail-fast result; the following no-op check passed.

The later operator instruction to complete the real build expanded the cutover beyond this ticket's original no-pool boundary. The real host imported both known GUIDs read-only first, verified the final snapshots and exact topology, exported them, then explicitly renamed and mounted them as `ark` and `black-box`. That operator action is recorded here but remains outside automatic reconciliation.

Evidence is under [`artifacts/cutover-2026-09-05/`](../artifacts/cutover-2026-09-05/). The clean deployment branch is `agent/pod042-cutover`; the primary working tree and its staged review state were left untouched.
