# Docker Stack Role Design

## Problem

Deploying Docker stacks currently requires repetitive tasks per stack:

1. Template compose file
2. Find and template config files (if any)
3. Deploy the compose stack

This leads to 3+ tasks per stack, which is verbose.

## Goals

- **One task per stack** in the playbook
- **Thin layer** — convenience wrapper, not Helm-for-Docker
- **Native Ansible feel** — use group_vars, not custom config files
- **Container-based organization** — config files grouped by container name

## Solution

A `docker_stack` role that consolidates the repetitive tasks, with configuration living in standard Ansible locations.

## Configuration

### Variables in `inventory/group_vars/truenas.yml`

```yaml
# Docker configuration
docker:
  # Base path for container configs: {config_base}/{stack}/{container}/...
  config_base: /mnt/performance/docker
  # User/group for containers
  user:
    puid: 950
    pgid: 544
    id: "950:544"

# Network ranges (macvlan iprange):
#   trusted:  192.168.1.0/24 (host network)
#   iot:      192.168.3.224/27 (192.168.3.224-255)
#   external: 192.168.5.224/27 (192.168.5.224-255)
#   personal: 192.168.6.224/27 (192.168.6.224-255)
lan:
  trusted:
    truenas:
      ip: 192.168.1.68
      ports:
        plex: 32400
      domain: truenas.thurstons.house

  iot:
    frigate:
      ip: 192.168.3.227
      ports:
        web_ui: 5000
        rtsp: 8554
        webrtc: 8555
      domain: frigate.thurstons.house

  external:
    cloudflared:
      ip: 192.168.5.225
      ports: {}
    overseerr:
      ip: 192.168.5.227
      ports:
        web: 5055
      domain: overseerr.thurstons.house
    # ...

  personal:
    homepage:
      ip: 192.168.6.225
      ports:
        web: 80
      domain: dash.thurstons.house
    homepage_docker_socket_proxy:
      ip: 192.168.6.234
      ports:
        docker_api: 2375
    # ...
```

The `lan` structure keeps IPs, ports, and domains together per container. This ensures a single source of truth when containers reference each other (e.g., homepage config pointing to the docker socket proxy).

### Directory Structure (Local)

```
ansible/stacks/<stack_name>/
├── compose.yaml.j2           # Required: Jinja2 compose template
└── <container_name>/         # Optional: per-container config directories
    └── <path/to/config>/     # Arbitrary nested structure
        ├── settings.yaml.j2
        └── nested.conf
```

Container directories are named to match the container they configure. The directory structure within each container folder is preserved exactly on the remote.

**Example: homepage stack**

```
ansible/stacks/homepage/
├── compose.yaml.j2
└── homepage/                 # Config for 'homepage' container
    └── app/config/
        ├── bookmarks.yaml.j2
        ├── services.yaml.j2
        └── settings.yaml.j2
```

**Example: ddclient stack**

```
ansible/stacks/ddclient/
├── compose.yaml.j2
└── ddclient/                 # Config for 'ddclient' container
    └── config/
        ├── ddclient.conf.j2
        └── trigger-tofu-apply.sh
```

### Directory Structure (Remote)

```
/mnt/performance/docker/
├── stacks/<stack_name>/      # Compose files
│   └── compose.yaml
└── <stack_name>/             # Runtime data + config
    └── <container_name>/     # Mirrors local container directory structure
        └── <path/to/config>/
            ├── settings.yaml
            └── nested.conf
```

The container directory structure is preserved exactly — the path from `<container_name>/` onward is replicated on the remote.

## Role Interface

```yaml
- name: Deploy homepage stack
  tags: [docker-stack-role, homepage]
  ansible.builtin.include_role:
    name: docker_stack
    apply:
      tags: [docker-stack-role, homepage]
  vars:
    docker_stack_name: homepage
```

That's it. The role auto-discovers container directories and syncs them to the appropriate remote paths.

### Role Parameters

| Parameter           | Required | Default | Description                                        |
| ------------------- | -------- | ------- | -------------------------------------------------- |
| `docker_stack_name` | yes      | —       | Name of the stack (matches directory in `stacks/`) |

Note: The `docker_stack_` prefix complies with ansible-lint's production profile.

## Compose Template Example

```yaml
# stacks/homepage/compose.yaml.j2
services:
  homepage-docker-socket-proxy:
    image: ghcr.io/tecnativa/docker-socket-proxy:latest
    container_name: homepage-docker-socket-proxy
    networks:
      personal:
        ipv4_address: {{ lan.personal.homepage_docker_socket_proxy.ip }}
    ports:
      - "{{ lan.personal.homepage_docker_socket_proxy.ports.docker_api }}:{{ lan.personal.homepage_docker_socket_proxy.ports.docker_api }}"

  homepage:
    image: ghcr.io/gethomepage/homepage:latest
    container_name: homepage
    networks:
      personal:
        ipv4_address: {{ lan.personal.homepage.ip }}
    ports:
      - "{{ lan.personal.homepage.ports.web }}:{{ lan.personal.homepage.ports.web }}"
    environment:
      PUID: {{ docker.user.puid }}
      PGID: {{ docker.user.pgid }}
      PORT: {{ lan.personal.homepage.ports.web }}
      HOMEPAGE_ALLOWED_HOSTS: {{ lan.personal.homepage.domain }}
    volumes:
      # docker.config_dir is set by the role to {config_base}/{stack_name}
      - {{ docker.config_dir }}/homepage/app/config:/app/config
    # ...

networks:
  personal:
    external: true
```

Note: The role sets `docker.config_dir` to `{docker.config_base}/{stack_name}` (e.g., `/mnt/performance/docker/homepage`), so compose templates can reference container config paths directly.

## File Handling

The role handles both Jinja templates and plain files:

| Local file                     | Remote result                                   |
| ------------------------------ | ----------------------------------------------- |
| `compose.yaml.j2`              | Templated → `stacks/{stack}/compose.yaml`       |
| `compose.yaml`                 | Copied → `stacks/{stack}/compose.yaml`          |
| `{container}/path/foo.yaml.j2` | Templated → `{stack}/{container}/path/foo.yaml` |
| `{container}/path/foo.yaml`    | Copied → `{stack}/{container}/path/foo.yaml`    |

Stack-level files (compose.yaml) go to `stacks/{stack}/`. Container directories and their contents go to `{stack}/{container}/...` with ownership set to `docker.user.puid:docker.user.pgid`.

Use `.j2` extension only when you need Jinja templating. Plain files pass through unchanged.

## Benefits

1. **One task per stack** — role handles template + config + deploy
2. **Container-based organization** — config files grouped by container, mirroring remote layout
3. **Native Ansible** — group_vars for config, not custom files
4. **Single source of truth** — IPs, ports, and domains in one place for cross-container references
5. **Thin abstraction** — auto-discovers containers, no config needed beyond stack name

## Migration Path

1. Create `inventory/group_vars/truenas.yml` with `docker` and `lan` structure
2. Create the `docker_stack` role
3. Migrate stacks one at a time:
   - Move config files into `<container_name>/` subdirectories matching remote layout
   - Replace multi-task blocks with single role include
4. Remove `config/docker.yml` and `vars_files` reference once all stacks migrated
