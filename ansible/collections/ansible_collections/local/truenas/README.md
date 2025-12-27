# local.truenas

Thin Ansible wrappers around TrueNAS SCALE's `midclt` CLI.

## Features

- Direct 1:1 mapping to midclt API fields (no remapping)
- Full check_mode and diff support
- Minimal abstraction - just handles the query/compare/create/update/delete pattern

## Requirements

- TrueNAS SCALE (tested on Electric Eel 24.10+)
- SSH access to TrueNAS with `become: true`
- Environment: `middleware_method: midclt`

## Modules

| Module               | midclt resource      | Description               |
| -------------------- | -------------------- | ------------------------- |
| `initshutdownscript` | `initshutdownscript` | Init/shutdown scripts     |
| `pool_snapshottask`  | `pool.snapshottask`  | Periodic snapshot tasks   |
| `pool_scrub`         | `pool.scrub`         | Pool scrub tasks          |
| `sharing_smb`        | `sharing.smb`        | SMB shares                |
| `sharing_nfs`        | `sharing.nfs`        | NFS shares                |
| `service`            | `service`            | Service enable/start/stop |
| `smart_test`         | `smart.test`         | SMART test schedules      |

## Usage

```yaml
- hosts: truenas
  become: true
  environment:
    middleware_method: midclt
  tasks:
    - name: Enable Wake-on-LAN at boot
      local.truenas.initshutdownscript:
        comment: "enable WOL"
        type: COMMAND
        command: "ethtool -s enp3s0 wol g"
        when: POSTINIT
        enabled: true
        state: present

    - name: Enable SMB service
      local.truenas.service:
        name: cifs
        enabled: true
        state: started

    - name: Create 6-hourly snapshots
      local.truenas.pool_snapshottask:
        dataset: performance
        naming_schema: "auto-%Y-%m-%d_%H-%M"
        recursive: true
        lifetime_value: 3
        lifetime_unit: DAY
        schedule:
          minute: "0"
          hour: "*/6"
          dom: "*"
          month: "*"
          dow: "*"
        state: present

    - name: Weekly scrub
      local.truenas.pool_scrub:
        pool_name: performance
        threshold: 35
        schedule:
          minute: "0"
          hour: "4"
          dom: "*"
          month: "*"
          dow: "tue"
        state: present

    - name: Create SMB share
      local.truenas.sharing_smb:
        name: documents
        path: /mnt/pool/documents
        state: present

    - name: Create NFS share
      local.truenas.sharing_nfs:
        path: /mnt/pool/data
        networks:
          - 192.168.1.0/24
        maproot_user: root
        state: present
```

## Design Pattern

Each module follows the same pattern:

1. **Query**: Find existing resource by identity field(s)
2. **Compare**: Diff current state vs desired state
3. **Act**: Create, update, or delete as needed
4. **Report**: Return changed status and diff output

## Architecture

```
plugins/
├── action/                # Run on controller (Python 3.12+)
│   ├── initshutdownscript.py
│   ├── pool_snapshottask.py
│   ├── pool_scrub.py
│   ├── service.py
│   ├── sharing_nfs.py
│   ├── sharing_smb.py
│   └── smart_test.py
├── modules/               # Docs-only stubs
│   └── *.py
└── plugin_utils/
    └── midclt.py          # Shared MidcltClient, format_diff
```

Action plugins run locally on the controller with full Python 3.12+ features.
Only raw `midclt call` commands execute on TrueNAS via SSH.

The `MidcltClient` class provides typed methods for all midclt operations:
- `query(resource, filters)` → `list[ResourceRecord]`
- `query_one(resource, filters)` → `ResourceRecord | None`
- `create(resource, payload)` → `CreateResult` (with `.id` and optional `.record`)
- `update(resource, id, changes)` → `None`
- `delete(resource, id)` → `None`
- Service-specific: `service_query`, `service_start`, `service_stop`, `service_restart`
