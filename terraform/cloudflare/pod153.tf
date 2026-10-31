# pod153's MCP servers listen on its loopback only, so it runs its own tunnel connector.
resource "random_password" "pod153_tunnel_secret" {
  length  = 64
  special = false
}

resource "cloudflare_zero_trust_tunnel_cloudflared" "pod153" {
  account_id = local.account_id
  name       = "pod153"
  secret     = base64encode(random_password.pod153_tunnel_secret.result)
  config_src = "cloudflare"
}

resource "cloudflare_zero_trust_tunnel_cloudflared_config" "pod153" {
  account_id = local.account_id
  tunnel_id  = cloudflare_zero_trust_tunnel_cloudflared.pod153.id
  depends_on = [cloudflare_zero_trust_access_application.pod153_mcp]

  config {
    # Both servers reject Host headers other than their loopback address.
    ingress_rule {
      hostname = "pod153-mcp.${local.zone_name}"
      path     = "^/servers/messages/"
      service  = "http://127.0.0.1:7363"

      origin_request {
        http_host_header = "127.0.0.1:7363"
      }
    }

    ingress_rule {
      hostname = "pod153-mcp.${local.zone_name}"
      path     = "^/reminders$"
      service  = "http://127.0.0.1:7362"

      origin_request {
        http_host_header = "127.0.0.1:7362"
      }
    }

    ingress_rule {
      service = "http_status:404"
    }
  }
}

resource "cloudflare_record" "pod153_mcp" {
  zone_id = local.zone_id
  name    = "pod153-mcp"
  type    = "CNAME"
  content = cloudflare_zero_trust_tunnel_cloudflared.pod153.cname
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

  include {
    service_token = [cloudflare_zero_trust_access_service_token.executor.id]
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "cloudflare_zero_trust_access_application" "pod153_mcp" {
  account_id           = local.account_id
  name                 = "pod153 MCP"
  domain               = "pod153-mcp.${local.zone_name}"
  type                 = "self_hosted"
  app_launcher_visible = false
  policies             = [cloudflare_zero_trust_access_policy.executor_service_auth.id]
}
