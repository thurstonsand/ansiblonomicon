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
    "anypod.${local.zone_name}/admin/*"
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
