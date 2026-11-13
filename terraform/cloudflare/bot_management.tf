resource "cloudflare_bot_management" "default" {
  zone_id    = local.zone_id
  enable_js  = true
  fight_mode = true

  # Retired by Cloudflare in favour of the separate Search, Training and Agent controls below.
  ai_bots_protection = "disabled"

  # robots.txt policy per kind of AI crawler.
  aisearch    = "disabled"
  ai_training = "disallow"
  ai_user     = "only_on_ad_pages"
  ai_agents = {
    anthropic_agent = "disabled"
    google_agent    = "disabled"
    instinct        = "disabled"
    muse            = "disabled"
    openai_agent    = "disabled"
  }

  # The link maze for AI scrapers that ignore robots.txt.
  crawler_protection      = "enabled"
  content_bots_protection = "disabled"
}
