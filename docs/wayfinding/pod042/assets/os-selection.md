# OS selection for pod042

*Research completed 2026-07-24; Arch-family assessment added 2026-07-24.*

## Recommendation

Run **Debian 13 (trixie) stable**, provisioned from its official `generic` amd64 cloud image with cloud-init, on the existing UEFI/KVM/VirtIO shape. Keep the base in stable; do not reinstate a `sid` source or pin. Put fast-moving developer runtimes and CLIs under their native, already-established managers (`mise`, `uv`, `npm`, `cargo`, and `go`), and add `trixie-backports` only for a named package with a demonstrated need.

This is the lowest-risk match for pod042: Debian calls 13 its current production/stable release and supports it through 2028, with LTS through June 2030. The existing OpenClaw playbook is explicitly apt-shaped—apt update/dist-upgrade, `apt_repository`, Debian package names, and Debian `.deb` external repositories—and its reusable roles otherwise mostly manage user-space tools and systemd. A fresh pod042 playbook can reuse the proven roles without turning OS selection into a package-manager-port.

Use the official **`generic`** cloud image rather than `genericcloud`: Debian says both use cloud-init, but `genericcloud` has a reduced driver set. The known VirtIO hardware should work with either, but the few saved drivers do not justify making first boot less tolerant of a TrueNAS VM-model change. Official images include qcow2 artifacts, so clean NoCloud provisioning does not need an installer ISO.

### Freshness policy

The old `tmux` sid pin was an unmanaged distribution crossover, not a package strategy. Trixie has tmux 3.5a and current `trixie-backports` has 3.6b; if 3.5a is insufficient, install only `tmux/trixie-backports` and record why. Debian explicitly recommends selecting individual backports, and backports are rebuilt for stable. Do **not** use a blanket `-t trixie-backports`, a global preference, or any `sid` source.

This is enough because the agent-oriented development surface is not constrained to Debian’s release cadence: the incumbent already installs Node from NodeSource, mise, uv, Rust, and Go tooling outside the distribution. Specify versions in their respective managers where reproducibility matters. A dev box that needs an entire rolling OS to obtain one terminal multiplexer has chosen the wrong update boundary.

### Unattended-operation boundary

Enable `unattended-upgrades` for Debian security updates and retain a periodic self-converge timer for repository configuration, declared apt packages, and user-level tool refreshes. Debian documents `unattended-upgrades` as its automatic-update mechanism. The two loops need an explicit apt-lock policy (the converge service waits/retries rather than racing the daily updater) and visible logs; that implementation belongs to the self-management ticket.

Treat the resident agent as a consumer of a managed machine, not the authority that changes the base OS. It can invoke the converger or report failure, while the repository remains the desired-state source.

## Runner-up: Ubuntu Server 26.04 LTS minimal

Choose **Ubuntu Server 26.04 LTS minimal** only if newer baseline system packages or Canonical’s longer five-year standard-support window materially outweigh a small but real migration audit. It has official minimal cloud images, released cloud images with KVM/VirtIO launch guidance, cloud-init, and the same apt/unattended-upgrades family. Ubuntu 26.04 LTS receives security and critical fixes through April 2031.

It is technically viable and is the only credible alternate with a similarly low operational cost. But it is not a drop-in: the OpenClaw configuration currently declares Debian-specific package names (`fd-find`/`fdfind`) and Debian repository URLs, notably 1Password. Reuse the roles, but audit every apt package, repository, keyring, path, and the cloud-image default user before declaring the new playbook portable. That is deliberate migration work for a modest benefit, so Debian remains the recommendation.

## Arch Linux assessment

**Vanilla Arch is technically excellent for the guest, but not for pod042’s unattended-operation contract.** Its official `arch-boxes` cloud image is a qcow2 artifact with cloud-init preinstalled, and Arch documents VirtIO support in its Linux guest. So clean NoCloud provisioning, UEFI, KVM, VirtIO disk/NIC, two cores, and modest RAM are not objections. `pacman` and the official repositories also deliver precisely the package freshness the user values.

The failure is the update boundary. Arch’s own system-maintenance guidance says to read Arch News before upgrades because out-of-the-ordinary user intervention is announced there, warns that unexpected upgrade problems can need immediate intervention, and requires full-system upgrades: partial upgrades such as `pacman -Sy package` are unsupported. It further says AUR packages must be carefully upgraded/rebuilt across soname bumps, are unsupported, and remain the user’s responsibility. The current official News archive includes manual-intervention notices and an AUR malicious-package incident. A systemd timer can run `pacman -Syu`, but that automates the action Arch expects a responsible operator to review; it is not an official unattended-upgrade policy comparable to Debian’s security-focused `unattended-upgrades`.

A resident agent improves observation but cannot safely decide whether an Arch News intervention applies, merge `.pacnew` configuration, or approve/review changed AUR PKGBUILDs. Letting an autonomous agent do those things would trade the sid smell for a larger, moving trust boundary. Automated Arch is reasonable only after changing the requirement to **monitored, manually approved full upgrades**, with a fresh VM/ZFS rollback point, a preflight that blocks on unread News, no AUR in the base image, and an operator responsible for upgrade failures. That is a fine personal workstation posture. It is not “stable under fully unattended operation.”

Arch also costs more than the existing playbook. `ansible/archlinux.config.yml` currently only declares empty `pacman_packages`/`aur_packages`; the sole Arch branch in `ansible/playbooks/macos.yml` is a placeholder debug task. pod042 would need new pacman/repository/bootstrap logic, package-name and path audit, a replacement for the Debian 1Password repository, and a policy for every AUR package. The portable roles remain useful, but the OS layer is not already implemented.

There is no Arch-family derivative that changes this result for this x86_64 server VM. Omarchy explicitly positions itself around **Workstations**, so it adds desktop opinion rather than a server lifecycle. Manjaro’s stable branch delays Arch packages through its own testing branches, but that creates a second repository lifecycle and does not supply an LTS/server update model; it also weakens the usual “current Arch package/AUR” expectation. A derivative is more moving infrastructure, not an answer to unattended upgrades. Use vanilla Arch only if owning that rolling-maintenance discipline is a positive goal; do not use a desktop derivative to simulate a server distribution.

**Verdict: keep Debian 13 as the recommendation and Ubuntu 26.04 LTS minimal as runner-up.** Arch wins freshness and user affinity, and passes the KVM/cloud-init gate, but loses the ticket’s decisive unattended-stability and repository-fit axes. Debian’s scoped backports plus native dev-tool managers give pod042 current developer tooling without making every OS update an operator decision.

## Alternatives considered

| Option | What it gets right | What it costs pod042 | Verdict |
| --- | --- | --- | --- |
| **Arch Linux** | Latest stable packages, fast `pacman`, official cloud-init qcow2, and Linux/VirtIO guest support. | Arch requires reviewed full-system upgrades; partial upgrades are unsupported, News can require manual intervention, and AUR packages require manual review/rebuild. The repo has only an Arch config stub and a placeholder playbook branch. | Excellent personally tended dev workstation; reject for fully unattended pod042. |
| **Fedora Server** | Very fresh developer packages; official qcow2 cloud image path; `dnf-automatic` supports scheduled updates. | Rebuild all apt/repository/bootstrap logic around DNF and RPM vendor repos, audit package names and paths, and perform Fedora release upgrades at least yearly. Fedora releases about every six months and are maintained about 13 months. | Good workstation/dev VM; wrong maintenance cadence and migration cost for an unattended utility VM. |
| **Fedora CoreOS** | Purpose-built, minimal, automatically updating, and has immutable/rollback-style deployment semantics; QEMU images and Ignition are first-class. | It is a container-host OS, provisioned with Ignition rather than cloud-init, and rpm-ostree layering/reboots conflict with iterative apt-style Ansible convergence. The resident agent’s mutable CLI/toolchain environment would need a separate container/toolbox or bespoke layering design. | Strong for a dedicated container node, not for this SSH-first dev and automation host. |
| **openSUSE MicroOS** | Small, rolling, transactional Btrfs snapshots; automated updates and rollback make failed OS updates recoverable. | Its container-workload posture and transactional package changes require rebooted snapshots. Replace apt tasks/repositories with zypper/`transactional-update`, adapt Ansible for a read-only root, and accept rolling-release churn. Validate the chosen raw/cloud image and first-boot mechanism before any implementation. | Attractive atomic model, but an unnecessary platform rewrite for pod042. |
| **NixOS** | Declarative system closure, reproducible dev environments, native QEMU/KVM image-building support. | It only pays off if this repository makes Nix/flake configuration—not Ansible—the system authority. Otherwise every apt bootstrap, package, service, user, secret, and update pattern becomes a parallel configuration stack; cloud-init/image provisioning also needs a purpose-built Nix path. | A valid new infrastructure direction, not a lean replacement under the current Ansible contract. |

## Decision criteria and evidence

### Existing repository fit

`ansible/playbooks/openclaw.yml` manages the OS with `ansible.builtin.apt` and `apt_repository`, including a full upgrade and Debian sid pinning. `ansible/openclaw.config.yml` supplies Debian package names and Debian `.deb` repositories. In contrast, `system_maintenance`, `language_tools`, `agent_harness`, `chezmoi`, `sessions`, and `shpool` principally depend on systemd, shell utilities, and user-space runtime managers. Debian preserves the high-value reusable portion and lets the fresh playbook delete the sid exception.

### Source notes

- [Debian Releases](https://www.debian.org/releases) — Debian 13/trixie is current stable; production recommendation; EOL 2028-08-09 and LTS end 2030-06-30.
- [Debian Official Cloud Images](https://cdimage.debian.org/images/cloud/) — `generic` runs cloud-init in general environments; `genericcloud` differs by reduced kernel drivers; Debian publishes qcow2 artifacts.
- [Debian Backports instructions](https://backports.debian.org/Instructions) and [Backports policy overview](https://backports.debian.org/) — trixie-backports setup and the recommendation to select individual packages rather than use all backports.
- [Debian tmux tracker](https://tracker.debian.org/pkg/tmux) — stable is 3.5a-3 and stable-backports is 3.6b-1~bpo13+1 as checked 2026-07-24.
- [Debian unattended upgrades](https://wiki.debian.org/UnattendedUpgrades) — Debian’s configuration path for automatic updates.
- [Ubuntu 26.04 LTS release notes](https://documentation.ubuntu.com/release-notes/26.04) — security and critical fixes through April 2031.
- [Ubuntu 26.04 released cloud image](https://cloud-images.ubuntu.com/releases/server/server/26.04/release) — released amd64 cloud image and KVM VirtIO guidance; [minimal cloud image documentation](https://documentation.ubuntu.com/public-cloud/all-clouds-explanation/ubuntu-base-and-minimal-images/) documents its minimal-image family; [automatic updates](https://ubuntu.com/server/docs/how-to/software/automatic-updates) documents unattended-upgrades.
- [Arch Linux on a VPS](https://wiki.archlinux.org/title/Arch_Linux_on_a_VPS) and [QEMU/VirtIO](https://wiki.archlinux.org/title/QEMU) — official `arch-boxes` cloud image with cloud-init, qcow2 use, and Arch Linux guest VirtIO support.
- [Arch system maintenance](https://wiki.archlinux.org/title/System_maintenance), [pacman](https://wiki.archlinux.org/title/Pacman), and [Arch News](https://archlinux.org/news/) — reviewed upgrades, unsupported partial upgrades, manual intervention notices, and current AUR security incident history.
- [Arch User Repository](https://wiki.archlinux.org/title/Arch_User_Repository) — AUR PKGBUILDs are user-maintained, unsupported, and require users to rebuild dependent packages after library changes; [Omarchy](https://omarchy.org/) is explicitly workstation-oriented; [Manjaro branches](https://wiki.manjaro.org/index.php/Switching_Branches) documents its delayed stable branch.
- [Fedora lifecycle](https://docs.fedoraproject.org/en-US/releases/lifecycle/) and [automatic updates](https://docs.fedoraproject.org/en-US/quick-docs/autoupdates/) — six-month releases with roughly 13 months maintenance and `dnf-automatic` support.
- [Fedora CoreOS download](https://fedoraproject.org/coreos/download?stream=stable) and [CoreOS FAQ](https://github.com/coreos/fedora-coreos-docs/blob/main/modules/ROOT/pages/faq.adoc) — automatic-update, container-focused positioning, stream model, disk images, Ignition, and update tooling.
- [openSUSE MicroOS](https://microos.opensuse.org/) and [SUSE transactional-update documentation](https://documentation.suse.com/sle-micro/6.2/html/Micro-transactional-updates/index.html) — rolling/container focus, transactional snapshots, reboot activation, and systemd-timer updates.
- [NixOS virtual machines](https://nix.dev/tutorials/nixos/nixos-configuration-on-vm.html) and [NixOS QEMU VM module](https://github.com/NixOS/nixpkgs/blob/master/nixos/modules/virtualisation/qemu-vm.nix) — declarative VM configuration and qcow2/KVM support.
