resource "cloudflare_zero_trust_access_application" "doppelclaude" {
  account_id           = local.account_id
  name                 = "Doppelclaude Origin"
  domain               = "doppelclaude-origin.${local.zone_name}"
  type                 = "self_hosted"
  app_launcher_visible = false
  policies             = [cloudflare_zero_trust_access_policy.service_auth.id]
}
