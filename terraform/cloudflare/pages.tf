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
