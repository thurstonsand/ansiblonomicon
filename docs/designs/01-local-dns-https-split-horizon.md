# Local DNS and HTTPS for Split-Horizon Access

## Problem Statement

When accessing homelab services from the LAN, traffic currently routes through Cloudflare Tunnel even for local destinations. This adds latency and creates a dependency on external infrastructure for local access.

**Goals:**

1. Resolve `*.thurstons.house` to local IPs (e.g., `192.168.5.235`) when on LAN
2. Maintain external access via Cloudflare Tunnel (unchanged)
3. Terminate HTTPS locally (cloudflared currently handles TLS at Cloudflare's edge)
4. Manage configuration declaratively (Terraform/Ansible)
5. Minimize LAN downtime risk — stability is paramount

## Decisions

### 1. UniFi DNS Records via Terraform

**Choice:** Use `ubiquiti-community/unifi` Terraform provider (v0.41.3+) for DNS record management.

**Why this provider:**

| Aspect             | paultyng/unifi | ubiquiti-community/unifi |
| ------------------ | -------------- | ------------------------ |
| Last release       | March 2023     | Nov 2025                 |
| DNS record support | ❌ None        | ✅ Full CRUD             |
| Maintenance        | Abandoned      | Active                   |
| Stars              | 567            | 61                       |
| Registry installs  | N/A            | 93.5K                    |

The repos are **fully diverged** — ubiquiti-community does not merge from paultyng. The fork was created because Paul Tyng (former HashiCorp) stopped active development. The community fork adds DNS records, API key auth, WireGuard, and other features.

**How it works under the hood:**

- Uses official UniFi REST API endpoints (`/api/login`, `s/{site}/rest/{resource}`)
- Data models are **generated from official UniFi JAR files** (not reverse-engineered)
- The go-unifi SDK extracts `api/fields/*.json` from `ace.jar` to build Go structs
- Auto-detects controller type (classic vs UDM/UDM-Pro API paths)

**Risk level:** Medium. API is undocumented but stable; major UniFi updates may require provider updates.

### 2. Caddy for Local HTTPS Termination

**Choice:** Deploy Caddy on TrueNAS to terminate TLS for local traffic.

**Why Caddy:**

- Simple configuration (vs nginx/traefik complexity)
- Automatic HTTPS with Let's Encrypt DNS-01 challenge
- Native Cloudflare DNS plugin for certificate validation
- Single binary, no dependencies, excellent stability
- Widely adopted in homelab community

**Architecture:**

```
LAN Client → DNS (UDM) → Caddy IP → Caddy → Backend Service
                ↓
         arcane.thurstons.house = <caddy-ip> (A record)
         prowlarr.thurstons.house = <caddy-ip> (A record)
         aig.thurstons.house = <caddy-ip> (A record)
         ... all services point to same Caddy instance
```

All local DNS entries resolve to the **same Caddy IP**. Caddy inspects the SNI (Server Name Indication) in the TLS handshake and routes to the appropriate backend based on hostname.

Caddy handles TLS termination using Let's Encrypt certs obtained via Cloudflare DNS challenge (no port 80 exposure needed).

**Certificate question:** Services accessed both internally and externally will have different certs (Let's Encrypt locally, Cloudflare edge externally). This is fine — browsers don't pin certificates by default. Both certs are:

- Valid for the same domain
- Signed by trusted CAs
- Not expired

The browser accepts either without complaint.

### 3. Not Using: Native UniFi UI Only

UniFi Network 9.x added native DNS record management (Settings → Policy Table → DNS). While this works, it's not declarative — changes would be manual and not tracked in version control.

We'll use Terraform for the declarative layer, which calls the same underlying API.

## Implementation Plan

**Important:** Caddy must be deployed and tested BEFORE DNS records are created. Otherwise, flipping DNS to a non-functional Caddy breaks all local access.

### Phase 1: Caddy Image Build Pipeline

- [ ] Create `apps/caddy/Dockerfile`:

  ```dockerfile
  FROM caddy:2-builder AS builder
  RUN xcaddy build --with github.com/caddy-dns/cloudflare

  FROM caddy:2-alpine
  COPY --from=builder /usr/bin/caddy /usr/bin/caddy
  ```

- [ ] Create GitHub Actions workflow to auto-build on:
  - Push to main (if Dockerfile changes)
  - Weekly schedule (to pick up new Caddy releases)
  - Manual trigger
- [ ] Push image to `ghcr.io/thurstonsand/caddy-cloudflare:latest`
- [ ] Tag with Caddy version for pinning (e.g., `2.9.1`)

### Phase 2: Caddy Stack Deployment

- [ ] Add Caddy stack to `ansible/stacks/caddy/`
- [ ] Reference image: `ghcr.io/thurstonsand/caddy-cloudflare:latest`
- [ ] Configure Cloudflare API token for DNS-01 challenge (store in 1Password)
  - Token needs: `Zone.Zone:Read` + `Zone.DNS:Edit` permissions
- [ ] Create Caddyfile with reverse proxy entries for each service
- [ ] Deploy via existing TrueNAS Ansible playbook
- [ ] Assign static IP on appropriate VLAN for Caddy container
- [ ] Set up Watchtower or similar to auto-pull new image versions

**Notes:**

- Building our own image avoids dependency on third-party maintainers
- GHA auto-builds keep image current without running Ansible
- Using plain Caddy with a static Caddyfile rather than `caddy-docker-proxy` (which auto-generates config from Docker labels) — explicit config is more reviewable

### Phase 3: Test Caddy (Before DNS Cutover)

- [ ] Add temporary `/etc/hosts` entry on test machine: `<caddy-ip> arcane.thurstons.house`
- [ ] Verify HTTPS works with valid Let's Encrypt cert
- [ ] Test multiple services through Caddy
- [ ] Confirm cert is issued and renewed correctly
- [ ] Remove `/etc/hosts` entry after testing

### Phase 4: Terraform Provider Setup

- [ ] Add `ubiquiti-community/unifi` provider to existing Terraform config
- [ ] Configure provider authentication (API key or credentials via 1Password)
- [ ] Test with a single non-critical service first

### Phase 5: DNS Cutover

- [ ] Create `unifi_dns_record` resources for each service requiring local access
- [ ] Start with one service, verify it works end-to-end
- [ ] Roll out remaining services
- [ ] Confirm external access still works via Cloudflare Tunnel

### Phase 6: Documentation & Cleanup

- [ ] Document which services are local-accessible vs external-only
- [ ] Add runbook for adding new services (Caddy entry + DNS record)
- [ ] Document rollback procedure

## Resources

### Terraform Provider

- **Registry:** https://registry.terraform.io/providers/ubiquiti-community/unifi/latest
- **GitHub:** https://github.com/ubiquiti-community/terraform-provider-unifi
- **DNS Record Docs:** https://registry.terraform.io/providers/ubiquiti-community/unifi/latest/docs/resources/dns_record

### Caddy

- **Official Docs:** https://caddyserver.com/docs/
- **Cloudflare DNS Plugin:** https://github.com/caddy-dns/cloudflare
- **Docker Image:** `caddy:2-alpine` (or custom build with DNS plugin)

### UniFi API Background

- **Official Site Manager API:** https://developer.ui.com/site-manager-api/ (read-only, cloud)
- **Local API Docs:** UniFi Network → Settings → Control Plane → Integrations
- **go-unifi SDK:** https://github.com/paultyng/go-unifi (upstream) / https://github.com/ubiquiti-community/go-unifi (fork)

## Example Terraform Config

```hcl
terraform {
  required_providers {
    unifi = {
      source  = "ubiquiti-community/unifi"
      version = "~> 0.41.3"
    }
  }
}

provider "unifi" {
  username = var.unifi_username
  password = var.unifi_password
  api_url  = "https://192.168.1.1"  # UDM address

  # Skip TLS verification for self-signed cert
  allow_insecure = true
}

resource "unifi_dns_record" "arcane" {
  name        = "arcane.thurstons.house"
  record_type = "A"
  value       = "192.168.5.235"
  enabled     = true
  ttl         = 300
}
```

## Example Caddyfile

```caddyfile
{
  email you@example.com
  acme_dns cloudflare {env.CLOUDFLARE_API_TOKEN}
}

arcane.thurstons.house {
  reverse_proxy 192.168.5.235:8080
}

# Additional services...
```

## Rollback Procedure

1. **DNS:** Delete Terraform-managed DNS records; UDM falls back to upstream DNS
2. **Caddy:** Stop Caddy container; traffic fails locally but external access via Cloudflare Tunnel remains unaffected
3. **Full rollback:** Remove DNS records + stop Caddy; all traffic routes through Cloudflare Tunnel as before

## Next Steps (Investigation)

- Is there a way to capture nextdns utility/cli installation on udmp?
- Is there a way to setup the ssh key/systemd service on udmp?
- If not the above, ansible?
