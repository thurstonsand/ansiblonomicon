resource "cloudflare_zero_trust_tunnel_cloudflared" "home" {
  account_id    = local.account_id
  name          = "home"
  tunnel_secret = "placeholder"

  lifecycle {
    prevent_destroy = true
    ignore_changes  = [tunnel_secret]
  }
}

resource "cloudflare_zero_trust_tunnel_cloudflared_config" "home" {
  account_id = local.account_id
  tunnel_id  = cloudflare_zero_trust_tunnel_cloudflared.home.id
  depends_on = [cloudflare_zero_trust_access_application.doppelclaude]

  config = {
    ingress = concat(
      [
        { hostname = local.zone_name, service = "http://caddy:80" },
        { hostname = "www.${local.zone_name}", service = "http://caddy:80" },
      ],
      [for app in local.tunnel_apps : { hostname = "${app.host}.${local.zone_name}", service = app.service }],
      [for app in local.internal_tunnel_apps : {
        hostname       = "${app.host}.${local.zone_name}"
        service        = app.service
        origin_request = merge(local.tunnel_origin_request_defaults, { no_tls_verify = app.no_tls_verify })
      }],
      [for app in concat(local.ssh_tunnel_apps, local.recovery_ssh_tunnel_apps) : {
        hostname = "${app.host}.${local.zone_name}"
        service  = "ssh://${app.ip}:${app.port}"
      }],
      [{ service = "http_status:404" }],
    )
  }
}

# DNS records for tunnel apps
resource "cloudflare_dns_record" "tunnel_app" {
  for_each = { for app in local.tunnel_apps : app.host => app }

  zone_id = local.zone_id
  name    = each.key
  type    = "CNAME"
  content = local.tunnel_cname_target
  proxied = true
  ttl     = 1
}

resource "cloudflare_dns_record" "internal_tunnel_app" {
  for_each = { for app in local.internal_tunnel_apps : app.host => app }

  zone_id = local.zone_id
  name    = each.key
  type    = "CNAME"
  content = local.tunnel_cname_target
  proxied = true
  ttl     = 1
}

# DNS records for SSH tunnel apps
resource "cloudflare_dns_record" "tunnel_ssh_app" {
  for_each = {
    for app in concat(local.ssh_tunnel_apps, local.recovery_ssh_tunnel_apps) :
    app.host => app
  }

  zone_id = local.zone_id
  name    = each.key
  type    = "CNAME"
  content = local.tunnel_cname_target
  proxied = true
  ttl     = 1
}
