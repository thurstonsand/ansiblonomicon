resource "cloudflare_zone_dnssec" "default" {
  zone_id = local.zone_id
}
