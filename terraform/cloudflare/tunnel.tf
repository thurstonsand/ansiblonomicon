resource "cloudflare_tunnel" "home" {
  account_id = local.account_id
  name       = "home"
  secret     = "placeholder"

  lifecycle {
    prevent_destroy = true
    ignore_changes  = [secret]
  }
}

resource "cloudflare_tunnel_config" "home" {
  account_id = local.account_id
  tunnel_id  = cloudflare_tunnel.home.id

  config {
    dynamic "ingress_rule" {
      for_each = local.tunnel_apps
      content {
        hostname = "${ingress_rule.value.host}.${local.zone_name}"
        service  = ingress_rule.value.service
      }
    }

    ingress_rule {
      service = "http_status:404"
    }
  }
}

# DNS records for tunnel apps
resource "cloudflare_record" "tunnel_app" {
  for_each = { for app in local.tunnel_apps : app.host => app }

  zone_id = local.zone_id
  name    = each.key
  type    = "CNAME"
  content = local.tunnel_cname_target
  proxied = true
  ttl     = 1
}


