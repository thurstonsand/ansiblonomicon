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

| Module               | midclt resource      | Description           |
| -------------------- | -------------------- | --------------------- |
| `initshutdownscript` | `initshutdownscript` | Init/shutdown scripts |

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
```

## Design Pattern

Each module follows the same pattern:

1. **Query**: Find existing resource by identity field(s)
2. **Compare**: Diff current state vs desired state
3. **Act**: Create, update, or delete as needed
4. **Report**: Return changed status and diff output
