resource "cloudflare_zone" "thurstons_house" {
  account_id = local.account_id
  paused     = false
  plan       = "free"
  type       = "full"
  zone       = local.zone_name

  lifecycle {
    prevent_destroy = true
  }
}
