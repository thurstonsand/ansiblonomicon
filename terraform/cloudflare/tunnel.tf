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
    ingress_rule {
      hostname = local.zone_name
      service  = "http://caddy:80"
    }

    ingress_rule {
      hostname = "www.${local.zone_name}"
      service  = "http://caddy:80"
    }

    dynamic "ingress_rule" {
      for_each = local.tunnel_apps
      content {
        hostname = "${ingress_rule.value.host}.${local.zone_name}"
        service  = ingress_rule.value.service
      }
    }

    dynamic "ingress_rule" {
      for_each = local.internal_tunnel_apps
      content {
        hostname = "${ingress_rule.value.host}.${local.zone_name}"
        service  = ingress_rule.value.service

        origin_request {
          no_tls_verify = ingress_rule.value.no_tls_verify
        }
      }
    }

    dynamic "ingress_rule" {
      for_each = concat(local.ssh_tunnel_apps, local.recovery_ssh_tunnel_apps)
      content {
        hostname = "${ingress_rule.value.host}.${local.zone_name}"
        service  = "ssh://${ingress_rule.value.ip}:${ingress_rule.value.port}"
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

resource "cloudflare_record" "internal_tunnel_app" {
  for_each = { for app in local.internal_tunnel_apps : app.host => app }

  zone_id = local.zone_id
  name    = each.key
  type    = "CNAME"
  content = local.tunnel_cname_target
  proxied = true
  ttl     = 1
}

# DNS records for SSH tunnel apps
resource "cloudflare_record" "tunnel_ssh_app" {
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
