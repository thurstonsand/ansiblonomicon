resource "cloudflare_pages_project" "tesla" {
  account_id        = local.account_id
  name              = "tesla"
  production_branch = "main"
}

resource "cloudflare_pages_domain" "tesla" {
  account_id   = local.account_id
  project_name = cloudflare_pages_project.tesla.name
  domain       = "tesla.${local.zone_name}"
}

resource "cloudflare_record" "tesla" {
  zone_id = local.zone_id
  name    = "tesla"
  type    = "CNAME"
  content = cloudflare_pages_project.tesla.subdomain
  proxied = true
  ttl     = 1
}
