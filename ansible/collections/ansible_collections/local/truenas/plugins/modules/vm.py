#!/usr/bin/python
# This module is implemented as an action plugin.
# This file exists only for documentation and argument validation.

DOCUMENTATION = """
---
module: vm
short_description: Manage opinionated TrueNAS SCALE virtual machines via midclt
description:
  - Creates and updates TrueNAS SCALE virtual machines and selected VM devices.
  - Runs as an action plugin on the controller - only midclt commands execute on TrueNAS.
  - Identity field is C(name).
  - Only devices declared in C(devices) are managed; undeclared devices are left untouched.
options:
  name:
    description:
      - VM name.
    type: str
    required: true
  state:
    description:
      - Desired VM definition state.
    type: str
    choices: [present, absent]
    default: present
  power_state:
    description:
      - Optional runtime power state after definition changes.
    type: str
    choices: [started, stopped, restarted]
  description:
    type: str
  autostart:
    type: bool
  memory:
    description:
      - VM memory in MiB.
    type: int
  min_memory:
    description:
      - Minimum VM memory in MiB.
    type: int
  vcpus:
    type: int
  cores:
    type: int
  threads:
    type: int
  cpu_mode:
    type: str
    choices: [CUSTOM, HOST-MODEL, HOST-PASSTHROUGH]
  cpu_model:
    type: str
  cpuset:
    type: str
  nodeset:
    type: str
  pin_vcpus:
    type: bool
  enable_cpu_topology_extension:
    type: bool
  trusted_platform_module:
    type: bool
  hyperv_enlightenments:
    type: bool
  bootloader:
    type: str
    choices: [UEFI, UEFI_CSM]
  bootloader_ovmf:
    type: str
  hide_from_msr:
    type: bool
  ensure_display_device:
    type: bool
  time:
    type: str
    choices: [LOCAL, UTC]
  shutdown_timeout:
    type: int
  arch_type:
    type: str
  machine_type:
    type: str
  uuid:
    type: str
  zvols:
    description:
      - ZFS volumes to ensure before VM devices are attached.
      - Existing zvols are not resized by this module.
    type: list
    elements: dict
    suboptions:
      name:
        description:
          - Full dataset name, for example C(performance/openclaw).
        type: str
        required: true
      volsize:
        description:
          - Zvol size in bytes.
        type: int
        required: true
      volblocksize:
        type: str
        default: 16K
      sparse:
        type: bool
      comments:
        type: str
  devices:
    description:
      - Selected devices to ensure on the VM.
      - Existing undeclared devices are ignored.
      - Device identity defaults by dtype: DISK path, NIC mac, DISPLAY dtype, USB device, CDROM path, RAW path.
    type: list
    elements: dict
    suboptions:
      dtype:
        type: str
        required: true
        choices: [NIC, DISK, CDROM, PCI, DISPLAY, RAW, USB]
      order:
        type: int
      identity:
        description:
          - Optional stable identity value used to match an existing device.
          - Usually unnecessary when the natural dtype identity is present.
        type: str
      attributes:
        description:
          - TrueNAS VM device attributes passed directly to vm.device.create/update.
          - Only provided attributes are compared and managed.
        type: dict
        default: {}
author:
  - Thurston Sandberg
"""

EXAMPLES = """
- name: Ensure OpenClaw VM exists
  local.truenas.vm:
    name: OpenClaw
    autostart: true
    memory: 12288
    min_memory: 12288
    vcpus: 1
    cores: 2
    threads: 1
    cpu_mode: HOST-PASSTHROUGH
    bootloader: UEFI
    ensure_display_device: true
    zvols:
      - name: performance/openclaw
        volsize: 107374182400
        volblocksize: 16K
        comments: OpenClaw VM boot disk
    devices:
      - dtype: DISK
        order: 1001
        attributes:
          type: VIRTIO
          path: /dev/zvol/performance/openclaw
          iotype: THREADS
      - dtype: NIC
        order: 1002
        attributes:
          type: VIRTIO
          mac: 00:a0:98:26:3f:c2
          nic_attach: br0
          trust_guest_rx_filters: false

- name: Model existing Home Assistant VM without touching USB devices
  local.truenas.vm:
    name: HAOS
    autostart: true
    memory: 8192
    min_memory: 4096
    vcpus: 1
    cores: 4
    threads: 1
    cpu_mode: HOST-PASSTHROUGH
    devices:
      - dtype: DISK
        attributes:
          path: /dev/zvol/performance/homeassistant
          type: VIRTIO
          iotype: THREADS
      - dtype: DISK
        identity: /dev/zvol/performance/haos-config
        attributes:
          path: /dev/zvol/performance/haos-config
          type: VIRTIO
          iotype: THREADS
      - dtype: NIC
        attributes:
          type: VIRTIO
          mac: 00:a0:98:70:3e:8b
          nic_attach: br0
"""

RETURN = """
id:
  description: The ID of the VM in TrueNAS.
  type: int
  returned: when present
changed_devices:
  description: Device changes made or planned.
  type: list
  returned: always
diff:
  description: Before/after state for changed resources.
  type: dict
  returned: when changed
"""
