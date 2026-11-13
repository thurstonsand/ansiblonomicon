# Provider v5 has no cloudflare_zone_settings_override, and OpenTofu refuses to read state that holds
# one, so it leaves state under v4 before v5 imports each setting as its own cloudflare_zone_setting.
removed {
  from = cloudflare_zone_settings_override.settings

  lifecycle {
    destroy = false
  }
}
