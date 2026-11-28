# pod153's MCP servers listen on its loopback only, so it runs its own tunnel connector.
resource "random_password" "pod153_tunnel_secret" {
  length  = 64
  special = false
}

resource "cloudflare_zero_trust_tunnel_cloudflared" "pod153" {
  account_id    = local.account_id
  name          = "pod153"
  tunnel_secret = base64encode(random_password.pod153_tunnel_secret.result)
  config_src    = "cloudflare"
}

resource "cloudflare_zero_trust_tunnel_cloudflared_config" "pod153" {
  account_id = local.account_id
  tunnel_id  = cloudflare_zero_trust_tunnel_cloudflared.pod153.id
  depends_on = [
    cloudflare_zero_trust_access_application.pod153_mcp,
    cloudflare_zero_trust_access_application.pod153_nurb,
    cloudflare_zero_trust_access_application.pod153_evidence,
  ]

  config = {
    ingress = [
      # RemCTL rejects Host headers other than its loopback address.
      {
        hostname       = "pod153-mcp.${local.zone_name}"
        path           = "^/reminders$"
        service        = "http://127.0.0.1:7362"
        origin_request = merge(local.tunnel_origin_request_defaults, { http_host_header = "127.0.0.1:7362" })
      },
      {
        hostname       = "pod153-mcp.${local.zone_name}"
        path           = "^/photos$"
        service        = "http://127.0.0.1:7366"
        origin_request = merge(local.tunnel_origin_request_defaults, { http_host_header = "127.0.0.1:7366" })
      },
      # Beeper Desktop's API for its chats, messages and accounts; not its setup or file routes.
      {
        hostname = "pod153-mcp.${local.zone_name}"
        path     = "^/v1/(accounts|chats|messages)(/.*)?$"
        service  = "http://127.0.0.1:23373"
      },
      # A sender's Matrix profile, for the Beeper app to name people who have left a chat.
      {
        hostname = "pod153-mcp.${local.zone_name}"
        path     = "^/_matrix/client/v3/profile/[^/]+$"
        service  = "http://127.0.0.1:23373"
      },
      # server/beeper_images.py: a message's image, shrunk for an agent.
      {
        hostname = "pod153-mcp.${local.zone_name}"
        path     = "^/beeper/images$"
        service  = "http://127.0.0.1:7364"
      },
      # nurb's whole serve, through the Caddy front that rewrites Host and Origin for this name.
      {
        hostname = "nurb.${local.zone_name}"
        service  = "http://10.10.10.53:7373"
      },
      # HearingTestAI's evidence index, its pictures and recordings, through the Caddy front that
      # serves the folder and withholds raw exports.
      {
        hostname = "evidence.${local.zone_name}"
        service  = "http://127.0.0.1:8766"
      },
      { service = "http_status:404" },
    ]
  }
}

resource "cloudflare_dns_record" "pod153_mcp" {
  zone_id = local.zone_id
  name    = "pod153-mcp"
  type    = "CNAME"
  content = "${cloudflare_zero_trust_tunnel_cloudflared.pod153.id}.cfargotunnel.com"
  proxied = true
  ttl     = 1
}

# Off the LAN only: UniFi answers nurb.thurstons.house with pod042's ingress at home.
resource "cloudflare_dns_record" "nurb" {
  zone_id = local.zone_id
  name    = "nurb"
  type    = "CNAME"
  content = "${cloudflare_zero_trust_tunnel_cloudflared.pod153.id}.cfargotunnel.com"
  proxied = true
  ttl     = 1
}

resource "cloudflare_zero_trust_access_service_token" "executor" {
  account_id = local.account_id
  name       = "Executor"
  # An expiring token would silently cut executor.sh off from pod153.
  duration = "forever"
}

resource "cloudflare_zero_trust_access_policy" "executor_service_auth" {
  account_id = local.account_id
  name       = "Executor Service Auth"
  decision   = "non_identity"

  include = [{ service_token = { token_id = cloudflare_zero_trust_access_service_token.executor.id } }]

  lifecycle {
    create_before_destroy = true
  }
}

resource "cloudflare_zero_trust_access_application" "pod153_mcp" {
  account_id                 = local.account_id
  name                       = "pod153 MCP"
  domain                     = "pod153-mcp.${local.zone_name}"
  type                       = "self_hosted"
  http_only_cookie_attribute = true
  app_launcher_visible       = false
  policies = [
    { id = cloudflare_zero_trust_access_policy.executor_service_auth.id, precedence = 1 },
  ]
}

# nurb runs whatever Python its parts say and its /api has no auth of its own, so Access admits
# only Thurston and Amp's own token.
resource "cloudflare_zero_trust_access_service_token" "amp" {
  account_id = local.account_id
  name       = "Amp"
  duration   = "forever"
}

resource "cloudflare_zero_trust_access_policy" "amp_service_auth" {
  account_id = local.account_id
  name       = "Amp Service Auth"
  decision   = "non_identity"

  include = [{ service_token = { token_id = cloudflare_zero_trust_access_service_token.amp.id } }]

  lifecycle {
    create_before_destroy = true
  }
}

resource "cloudflare_zero_trust_access_application" "pod153_nurb" {
  account_id                 = local.account_id
  name                       = "nurb"
  domain                     = "nurb.${local.zone_name}"
  type                       = "self_hosted"
  http_only_cookie_attribute = true
  session_duration           = "24h"
  auto_redirect_to_identity  = true
  allowed_idps               = [cloudflare_zero_trust_access_identity_provider.google.id]
  policies = [
    { id = cloudflare_zero_trust_access_policy.amp_service_auth.id, precedence = 1 },
    { id = cloudflare_zero_trust_access_policy.admin_access.id, precedence = 2 },
  ]
}

resource "cloudflare_dns_record" "evidence" {
  zone_id = local.zone_id
  name    = "evidence"
  type    = "CNAME"
  content = "${cloudflare_zero_trust_tunnel_cloudflared.pod153.id}.cfargotunnel.com"
  proxied = true
  ttl     = 1
}

# The evidence shows a real patient's hearing tests, symptoms and medications, so Access admits
# only Thurston and Mike, whose records they are and who wrote the app the rewrite replaces.
resource "cloudflare_zero_trust_access_policy" "evidence_viewers" {
  account_id       = local.account_id
  name             = "HearingTestAI Evidence Viewers"
  decision         = "allow"
  session_duration = "24h"

  include = [
    { email = { email = "mikebaden@bellsouth.net" } },
    { email = { email = "radarwaveforms@gmail.com" } },
  ]

  lifecycle {
    create_before_destroy = true
  }
}

# Mike signs in with Google if his address is a Google account and by one-time PIN if it is not,
# so the login page offers both instead of redirecting to one.
resource "cloudflare_zero_trust_access_application" "pod153_evidence" {
  account_id                 = local.account_id
  name                       = "HearingTestAI evidence"
  domain                     = "evidence.${local.zone_name}"
  type                       = "self_hosted"
  http_only_cookie_attribute = true
  session_duration           = "24h"
  auto_redirect_to_identity  = false
  allowed_idps = [
    cloudflare_zero_trust_access_identity_provider.google.id,
    cloudflare_zero_trust_access_identity_provider.onetimepin.id,
  ]
  policies = [
    { id = cloudflare_zero_trust_access_policy.admin_access.id, precedence = 1 },
    { id = cloudflare_zero_trust_access_policy.evidence_viewers.id, precedence = 2 },
  ]
}
