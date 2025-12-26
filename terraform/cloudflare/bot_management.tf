resource "cloudflare_bot_management" "default" {
  zone_id            = local.zone_id
  ai_bots_protection = "block"
  enable_js          = true
  fight_mode         = true
}
