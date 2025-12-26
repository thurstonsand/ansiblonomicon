resource "cloudflare_zone_settings_override" "settings" {
  zone_id = local.zone_id

  lifecycle {
    prevent_destroy = true
  }

  settings {
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
    zero_rtt            = "on"
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
    # Misc
    always_online    = "off"
    development_mode = "off"
    cname_flattening = "flatten_at_root"
    max_upload       = 100

    security_header {
      enabled            = false
      max_age            = 15552000
      include_subdomains = true
      preload            = true
      nosniff            = true
    }
  }
}
