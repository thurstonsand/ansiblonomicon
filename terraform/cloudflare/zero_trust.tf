resource "cloudflare_zero_trust_access_application" "truenas_app" {
  account_id                 = local.account_id
  name                       = "TrueNAS App"
  type                       = "self_hosted"
  http_only_cookie_attribute = true
  session_duration           = "730h"
  auto_redirect_to_identity  = true
  skip_interstitial          = true
  allowed_idps               = [cloudflare_zero_trust_access_identity_provider.google.id]
  destinations = [
    { type = "public", uri = "cli-proxy-api.${local.zone_name}" },
    { type = "public", uri = "anypod.${local.zone_name}/admin/*" },
  ]
  policies = [
    { id = cloudflare_zero_trust_access_policy.home_network_bypass.id, precedence = 1 },
    { id = cloudflare_zero_trust_access_policy.warp_bypass.id, precedence = 2 },
    { id = cloudflare_zero_trust_access_policy.service_auth.id, precedence = 3 },
    { id = cloudflare_zero_trust_access_policy.admin_access.id, precedence = 4 },
  ]
}

# Bypass Access for home network (by public IP)
# IP is derived from the home-ip DNS record, which ddclient keeps updated
resource "cloudflare_zero_trust_access_policy" "home_network_bypass" {
  account_id = local.account_id
  name       = "Home Network Bypass"
  decision   = "bypass"

  include = [
    { ip = { ip = "${local.home_ip}/32" } },
    { ip = { ip = "${var.parent_home_ip}/32" } },
  ]

  lifecycle {
    create_before_destroy = true
  }
}

# Bypass Access for WARP-connected devices
resource "cloudflare_zero_trust_device_posture_rule" "warp_connected" {
  account_id = local.account_id
  name       = "WARP Client Connected"
  type       = "warp"
  input      = {}
}

resource "cloudflare_zero_trust_access_policy" "warp_bypass" {
  account_id = local.account_id
  name       = "WARP Device Bypass"
  decision   = "bypass"

  include = [{ device_posture = { integration_uid = cloudflare_zero_trust_device_posture_rule.warp_connected.id } }]

  lifecycle {
    create_before_destroy = true
  }
}

resource "cloudflare_zero_trust_access_policy" "service_auth" {
  account_id = local.account_id
  name       = "Service Auth"
  decision   = "non_identity"

  include = [{ service_token = { token_id = cloudflare_zero_trust_access_service_token.onepassword.id } }]

  lifecycle {
    create_before_destroy = true
  }
}

resource "cloudflare_zero_trust_access_policy" "admin_access" {
  account_id       = local.account_id
  name             = "Admin Access"
  decision         = "allow"
  session_duration = "24h"

  include = [{ email = { email = "thurstonsand@gmail.com" } }]

  lifecycle {
    create_before_destroy = true
  }
}

resource "cloudflare_zero_trust_access_application" "warp_login" {
  account_id       = local.account_id
  name             = "Warp Login App"
  domain           = "${local.team_name}.cloudflareaccess.com/warp"
  type             = "warp"
  session_duration = "24h"
  policies = [
    { id = cloudflare_zero_trust_access_policy.admin_access.id, precedence = 1 },
  ]
}

# SSH Access via hostname-based tunnel ingress
# Uses cloudflared access ssh on the client side
resource "cloudflare_zero_trust_access_application" "ssh_access" {
  account_id                 = local.account_id
  name                       = "SSH Access"
  type                       = "self_hosted"
  http_only_cookie_attribute = true
  session_duration           = "24h"
  auto_redirect_to_identity  = true
  allowed_idps               = [cloudflare_zero_trust_access_identity_provider.google.id]
  destinations               = [for app in local.ssh_tunnel_apps : { type = "public", uri = "${app.host}.${local.zone_name}" }]
  policies = [
    { id = cloudflare_zero_trust_access_policy.admin_access.id, precedence = 1 },
  ]
}

resource "cloudflare_zero_trust_access_application" "recovery_ssh_access" {
  account_id                 = local.account_id
  name                       = "Recovery SSH Access"
  type                       = "self_hosted"
  http_only_cookie_attribute = true
  session_duration           = "24h"
  auto_redirect_to_identity  = true
  allowed_idps               = [cloudflare_zero_trust_access_identity_provider.google.id]
  destinations               = [for app in local.recovery_ssh_tunnel_apps : { type = "public", uri = "${app.host}.${local.zone_name}" }]
  policies = [
    { id = cloudflare_zero_trust_access_policy.service_auth.id, precedence = 1 },
    { id = cloudflare_zero_trust_access_policy.admin_access.id, precedence = 2 },
  ]
}

resource "cloudflare_zero_trust_access_application" "internal_access" {
  account_id                 = local.account_id
  name                       = "Internal Access"
  type                       = "self_hosted"
  http_only_cookie_attribute = true
  session_duration           = "24h"
  auto_redirect_to_identity  = true
  allowed_idps               = [cloudflare_zero_trust_access_identity_provider.google.id]
  destinations               = [for app in local.internal_tunnel_apps : { type = "public", uri = "${app.host}.${local.zone_name}" }]
  policies = [
    { id = cloudflare_zero_trust_access_policy.service_auth.id, precedence = 1 },
    { id = cloudflare_zero_trust_access_policy.admin_access.id, precedence = 2 },
  ]
}

resource "cloudflare_zero_trust_device_custom_profile" "thurstons_house_reroute" {
  account_id        = local.account_id
  name              = "thurstons.house reroute"
  description       = "Send specific traffic to thurstons.house through warp ONLY"
  enabled           = true
  precedence        = 1000
  lan_allow_minutes = 0
  match             = "identity.email in {\"thurstonsand@gmail.com\"}"

  service_mode_v2 = { mode = "warp" }
  include = [
    { host = "cli-proxy-api.${local.zone_name}" },
  ]
}

import {
  to = cloudflare_zero_trust_device_custom_profile.thurstons_house_reroute
  id = "${local.account_id}/0c44e984-7b42-4e71-b416-2637915fc7c8"
}
