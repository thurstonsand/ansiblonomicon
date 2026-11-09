# no9-type-s eGPU

no9-type-s drives an RTX 2070 in a Sonnet Breakaway Box 850T5 over Thunderbolt. Omarchy's NVIDIA setup assumes an internal GPU, so `omarchy-config` departs from it in a few places.

## Boot

- The NVIDIA modules load after Thunderbolt settles, not from the initramfs: `/etc/mkinitcpio.conf.d/nvidia.conf` is declared absent. Loaded from the initramfs, the driver bound a card attached at power-on before Thunderbolt had finished bringing it up; its display engine timed out (`Timed out waiting for core channel idle`), then the enclosure dropped off the bus under it.
- `omarchy/limine-entry-tool.d/egpu.conf` sets `thunderbolt.host_reset=0`. The firmware tunnels an enclosure attached at power-on, and the kernel's default USB4 host router reset tears that tunnel down after the driver has the card ([NVIDIA/open-gpu-kernel-modules#974](https://github.com/NVIDIA/open-gpu-kernel-modules/issues/974)). An AMD USB4 host saw soft lockups with this setting ([kernel bugzilla 221319](https://bugzilla.kernel.org/show_bug.cgi?id=221319)), so suspect it first if boot starts hanging.
- `omarchy/limine-entry-tool.d/crash-diagnostics.conf` turns soft and hard lockups into a panic and a reboot 15 seconds later, keeps the panic's last messages in EFI variables (read them from `/sys/fs/pstore` on the next boot), and enlarges the kernel log so a driver's error flood does not push out the start of the boot.
- Changes under `/etc/mkinitcpio.conf.d`, `/etc/modprobe.d`, or `/etc/limine-entry-tool.d` reach the next boot because `omarchy-config` reruns `limine-update` whenever one is newer than the UKI.

## Superwhisper

Superwhisper has no GPU setting and loads its models onto the strongest Vulkan device present when its service starts, about 3 GB on the RTX. A drop-in on its packaged user unit sets `VK_DRIVER_FILES` to Intel's Vulkan driver, so it stays on the integrated GPU and holds nothing on the eGPU when it is unplugged.

## Hyprland

Hyprland picks its GPUs once at startup from `AQ_DRM_DEVICES`, the first listed being the renderer, and does not adopt a GPU that appears later ([hyprwm/aquamarine#416](https://github.com/hyprwm/aquamarine/issues/416)). It also cannot choose a renderer per monitor ([hyprwm/aquamarine#318](https://github.com/hyprwm/aquamarine/issues/318)), so with Intel rendering, every frame for a monitor on the RTX is copied across Thunderbolt; that copy alone held the RTX at 85% and made the AW3423DW visibly choppy. `omarchy/uwsm/egpu` lists the NVIDIA card first in `AQ_DRM_DEVICES` whenever one is attached at login, so the RTX must be present before login, either attached at power-on or plugged in at the login screen. The built-in display then takes the copy instead, which matters little while docked with the lid closed.

Rendering on the RTX means Hyprland and every GPU-accelerated app in the session hold it open, so unplugging the eGPU while logged in takes the session down with it, and a driver losing a card it has open is the classic way to hang the whole machine. Log out before unplugging. Plugging in while logged in is safe, but the session ignores the new GPU until the next login.

## Hard freezes

A hot-plugged session froze about 18 minutes after the eGPU attached, with nothing in the journal. A repeat with the same load did not reproduce it. Reports from the same enclosure ([NVIDIA/open-gpu-kernel-modules#979](https://github.com/NVIDIA/open-gpu-kernel-modules/issues/979)) settle such freezes by disabling link power management: ASPM, PCIe port runtime suspend, Thunderbolt CLx (`thunderbolt.clx=0`), and NVIDIA runtime D3 (`NVreg_DynamicPowerManagement=0`). Prefer disabling ASPM and runtime suspend on the eGPU's own link through udev over the global `pcie_aspm=off` and `pcie_port_pm=off`, which cost idle battery everywhere.

A freeze takes the local journal with it, so capture from pod042 instead: `journalctl -f | ssh pod042 'cat >> ~/no9-egpu/journal.log'` keeps everything up to the last line that left the laptop.
