resource "cloudflare_zero_trust_access_application" "truenas_app" {
  account_id                = local.account_id
  name                      = "TrueNAS App"
  domain                    = "cli-proxy-api.${local.zone_name}"
  type                      = "self_hosted"
  session_duration          = "730h"
  auto_redirect_to_identity = true
  skip_interstitial         = true
  allowed_idps              = [cloudflare_zero_trust_access_identity_provider.google.id]
  # TODO: migrate to `destinations` block when upgrading to provider v5
  # Sticking with v4.x for now as Cloudflare recommends waiting until March 2025 for v5 to stabilize
  self_hosted_domains = [
    "cli-proxy-api.${local.zone_name}",
    "anypod.${local.zone_name}/admin/*",
    "openclaw.${local.zone_name}"
  ]
  policies = [
    cloudflare_zero_trust_access_policy.home_network_bypass.id,
    cloudflare_zero_trust_access_policy.warp_bypass.id,
    cloudflare_zero_trust_access_policy.service_auth.id,
    cloudflare_zero_trust_access_policy.admin_access.id
  ]
}

# Bypass Access for home network (by public IP)
# IP is derived from the storj DNS record, which ddclient keeps updated
resource "cloudflare_zero_trust_access_policy" "home_network_bypass" {
  account_id = local.account_id
  name       = "Home Network Bypass"
  decision   = "bypass"

  include {
    ip = [local.home_ip, var.parent_home_ip]
  }

  lifecycle {
    create_before_destroy = true
  }
}

# Bypass Access for WARP-connected devices
resource "cloudflare_zero_trust_device_posture_rule" "warp_connected" {
  account_id = local.account_id
  name       = "WARP Client Connected"
  type       = "warp"
}

resource "cloudflare_zero_trust_access_policy" "warp_bypass" {
  account_id = local.account_id
  name       = "WARP Device Bypass"
  decision   = "bypass"

  include {
    device_posture = [cloudflare_zero_trust_device_posture_rule.warp_connected.id]
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "cloudflare_zero_trust_access_policy" "service_auth" {
  account_id = local.account_id
  name       = "Service Auth"
  decision   = "non_identity"

  include {
    service_token = [cloudflare_zero_trust_access_service_token.onepassword.id]
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "cloudflare_zero_trust_access_policy" "admin_access" {
  account_id       = local.account_id
  name             = "Admin Access"
  decision         = "allow"
  session_duration = "24h"

  include {
    email = ["thurstonsand@gmail.com"]
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "cloudflare_zero_trust_access_application" "warp_login" {
  account_id           = local.account_id
  name                 = "Warp Login App"
  domain               = "${local.team_name}.cloudflareaccess.com/warp"
  type                 = "warp"
  session_duration     = "24h"
  app_launcher_visible = false
  policies             = [cloudflare_zero_trust_access_policy.admin_access.id]
}

# SSH Access via hostname-based tunnel ingress
# Uses cloudflared access ssh on the client side
resource "cloudflare_zero_trust_access_application" "ssh_access" {
  account_id                = local.account_id
  name                      = "SSH Access"
  type                      = "self_hosted"
  session_duration          = "24h"
  auto_redirect_to_identity = true
  allowed_idps              = [cloudflare_zero_trust_access_identity_provider.google.id]
  self_hosted_domains       = [for app in local.ssh_tunnel_apps : "${app.host}.${local.zone_name}"]
  policies = [
    cloudflare_zero_trust_access_policy.admin_access.id,
  ]
}

# VPC Service bindings for Workers → Tunnel origins
#
# VPC services are created via the Cloudflare Connectivity Directory API:
# POST /accounts/{account_id}/connectivity/directory/services
# See: https://developers.cloudflare.com/workers-vpc/configuration/vpc-services/
#
# Current VPC services (listed via GET /connectivity/directory/services):
# - openclaw-gateway (019bf380-8c74-7da0-8e8e-3a11fabeda32) → 192.168.1.90:18789
#   Used by wrangler/hooks OPENCLAW_SERVICE. Renamed from legacy clawdbot-gateway.
# - gog-gmail (019bf22a-39a7-7191-9721-e17c3bdf212d) → 192.168.1.90:8788
#   Legacy clawdbot Gmail endpoint; still exists in Cloudflare Connectivity Directory.
# - openclaw-telegram-webhook (019c8e1e-b11c-7d90-ab9b-5c5eba9d9897) → 192.168.1.90:8787 (9s)
#   Legacy 9s Telegram webhook endpoint; still exists in Cloudflare Connectivity Directory.
# - openclaw-telegram-webhook-2b (019c8e34-8b7e-7962-b03d-5e8fbe8d6715) → 192.168.1.90:8789 (2b)
#   Legacy 2B Telegram webhook endpoint; still exists in Cloudflare Connectivity Directory.
#
# TODO: Manage VPC services via Terraform when upgrading to CF provider v5
# Resource should be cloudflare_zero_trust_connectivity_service or similar

# Health webhook endpoint for iOS Shortcuts
# Uses service token auth - CF validates at edge before worker runs
resource "cloudflare_zero_trust_access_application" "health_webhook" {
  account_id       = local.account_id
  name             = "Health Webhook"
  type             = "self_hosted"
  session_duration = "24h"
  self_hosted_domains = [
    "hooks.${local.zone_name}/health",
    "hooks.${local.zone_name}/health/*"
  ]
  policies = [
    cloudflare_zero_trust_access_policy.service_auth.id,
  ]
}

# TODO: Add device profile with split tunnel in Include mode when upgrading to provider v5
# This will route only thurstons.house through WARP, everything else direct
# Resource: cloudflare_zero_trust_device_custom_profile
# For now, configure manually in Cloudflare dashboard:
# Settings → WARP Client → Device profiles → Create profile
# - Name: "Thurstons House Only"
# - Match: identity.email != ""
# - Split Tunnels: Include mode with:
#   - thurstons.house
#   - *.thurstons.house
#   - thurstonshouse.cloudflareaccess.com
