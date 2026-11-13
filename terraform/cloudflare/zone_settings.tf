locals {
  zone_settings = {
    # TLS/SSL
    ssl                      = "strict"
    min_tls_version          = "1.2"
    tls_1_3                  = "zrt"
    always_use_https         = "on"
    automatic_https_rewrites = "on"
    opportunistic_encryption = "on"
    tls_client_auth          = "on"

    # Performance
    brotli              = "on"
    early_hints         = "on"
    http3               = "on"
    "0rtt"              = "on"
    rocket_loader       = "on"
    websockets          = "on"
    ip_geolocation      = "on"
    ipv6                = "on"
    pseudo_ipv4         = "off"
    opportunistic_onion = "off"
    replace_insecure_js = "on"

    # Caching
    cache_level       = "aggressive"
    browser_cache_ttl = 14400

    # Security
    security_level      = "medium"
    challenge_ttl       = 1800
    browser_check       = "on"
    email_obfuscation   = "on"
    server_side_exclude = "on"
    hotlink_protection  = "on"
    privacy_pass        = "on"
    security_header = {
      strict_transport_security = {
        enabled            = false
        max_age            = 15552000
        include_subdomains = true
        preload            = true
        nosniff            = true
      }
    }

    # Misc
    always_online    = "off"
    development_mode = "off"
    cname_flattening = "flatten_at_root"
    max_upload       = 100
  }
}

resource "cloudflare_zone_setting" "this" {
  for_each = local.zone_settings

  zone_id    = local.zone_id
  setting_id = each.key
  value      = each.value

  lifecycle {
    prevent_destroy = true
  }
}

import {
  for_each = local.zone_settings
  to       = cloudflare_zone_setting.this[each.key]
  id       = "${local.zone_id}/${each.key}"
}
