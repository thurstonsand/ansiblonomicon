resource "cloudflare_zone" "thurstons_house" {
  account = { id = local.account_id }
  name    = local.zone_name
  paused  = false
  type    = "full"

  lifecycle {
    prevent_destroy = true
  }
}
