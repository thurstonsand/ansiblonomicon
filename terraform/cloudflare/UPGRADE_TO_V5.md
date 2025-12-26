# Cloudflare Provider v5 Upgrade Guide

This document tracks manual configurations and TODOs that should be addressed when upgrading from Cloudflare Terraform provider v4 to v5.

## Current Status

- **Provider version:** ~> 4.0
- **Recommended upgrade window:** After March 2025 (per Cloudflare's recommendation for v5 stability)

## Manual Configurations to Import

### Device Profile: "Thurstons House Only"

A custom WARP device profile was created manually in the Cloudflare dashboard because `cloudflare_zero_trust_device_custom_profile` is only available in v5.

**Location:** Cloudflare One → Team & Resources → Devices → Device profiles

**Configuration:**

- **Name:** Thurstons House Only
- **Expression:** User email in "thurstonsand@gmail.com"
- **Service Mode:** Gateway with WARP
- **Split Tunnels:** Include IPs and domains
  - `cli-proxy-api.thurstons.house`

**Action after upgrade:** Import using `cloudflare_zero_trust_device_custom_profile` resource or recreate via Terraform.

## Code TODOs

### 1. Migrate `self_hosted_domains` to `destinations` block

**File:** `zero_trust.tf` (line 10)

The `self_hosted_domains` argument is deprecated. Replace with `destinations` block:

```hcl
# Before (v4)
self_hosted_domains = [
  "cli-proxy-api.thurstons.house",
  "anypod.thurstons.house/admin/*"
]

# After (v5)
destinations {
  type = "public"
  uri  = "cli-proxy-api.thurstons.house"
}
destinations {
  type = "public"
  uri  = "anypod.thurstons.house/admin/*"
}
```

### 2. Migrate `cloudflare_tunnel` to `cloudflare_zero_trust_tunnel_cloudflared`

**File:** `tunnel.tf`

The `cloudflare_tunnel` resource is deprecated. Migrate to `cloudflare_zero_trust_tunnel_cloudflared`.

### 3. Add device profile via Terraform

**File:** `zero_trust.tf` (line 103)

Replace the TODO comment with actual resource once v5 is available:

```hcl
resource "cloudflare_zero_trust_device_custom_profile" "thurstons_house_only" {
  account_id  = local.account_id
  name        = "Thurstons House Only"
  description = "Routes only thurstons.house through WARP, everything else direct"
  enabled     = true
  precedence  = 100
  match       = "identity.email == \"thurstonsand@gmail.com\""

  service_mode_v2 = {
    mode = "warp"
  }

  include = [
    {
      host        = "cli-proxy-api.thurstons.house"
      description = "CLI Proxy API"
    },
    {
      host        = "thurstonshouse.cloudflareaccess.com"
      description = "Cloudflare Access login"
    }
  ]
}
```
