resource "cloudflare_bot_management" "default" {
  zone_id = local.zone_id
  # Cloudflare retired Block AI Bots for separate Search, Training and Agent controls, which provider
  # v4 cannot set; they live in the dashboard until the v5 upgrade.
  ai_bots_protection = "disabled"
  enable_js          = true
  fight_mode         = true
}
