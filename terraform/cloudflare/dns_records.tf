# Static DNS records (not managed via tunnel_apps inventory)

resource "cloudflare_record" "storj" {
  zone_id = local.zone_id
  name    = "storj"
  type    = "A"
  content = "0.0.0.0" # placeholder; ddclient owns the actual IP
  proxied = false
  ttl     = 1

  lifecycle {
    ignore_changes = [content] # ddclient dynamically updates this via Cloudflare API
  }
}

resource "cloudflare_record" "acme_challenge_ha" {
  zone_id = local.zone_id
  name    = "_acme-challenge.ha"
  type    = "CNAME"
  content = "_acme-challenge.fdsnaiutiizykhbtju3uhpmumkqhtmmi.ui.nabu.casa"
  comment = "nabu casa integration"
  proxied = false
  ttl     = 1
}

resource "cloudflare_record" "ha" {
  zone_id = local.zone_id
  name    = "ha"
  type    = "CNAME"
  content = "fdsnaiutiizykhbtju3uhpmumkqhtmmi.ui.nabu.casa"
  comment = "nabu casa integration"
  proxied = false
  ttl     = 1
}

resource "cloudflare_record" "screenshot" {
  zone_id = local.zone_id
  name    = "screenshot"
  type    = "CNAME"
  content = "cname.cleanshot.cloud"
  proxied = false
  ttl     = 1
}

resource "cloudflare_record" "sig1_domainkey" {
  zone_id = local.zone_id
  name    = "sig1._domainkey"
  type    = "CNAME"
  content = "sig1.dkim.${local.zone_name}.at.icloudmailadmin.com"
  proxied = false
  ttl     = 3600
}

resource "cloudflare_record" "root" {
  zone_id = local.zone_id
  name    = local.zone_name
  type    = "CNAME"
  content = local.tunnel_cname_target
  proxied = true
  ttl     = 1
}

resource "cloudflare_record" "www" {
  zone_id = local.zone_id
  name    = "www"
  type    = "CNAME"
  content = local.zone_name
  proxied = true
  ttl     = 1
}

# MX records
resource "cloudflare_record" "mx1" {
  zone_id  = local.zone_id
  name     = local.zone_name
  type     = "MX"
  content  = "mx01.mail.icloud.com"
  priority = 10
  proxied  = false
  ttl      = 3600
}

resource "cloudflare_record" "mx2" {
  zone_id  = local.zone_id
  name     = local.zone_name
  type     = "MX"
  content  = "mx02.mail.icloud.com"
  priority = 10
  proxied  = false
  ttl      = 3600
}

# TXT records
resource "cloudflare_record" "atproto_its" {
  zone_id = local.zone_id
  name    = "_atproto.its"
  type    = "TXT"
  content = "\"did=did:plc:qttpvwkp4xxt4zwa7mqh6qqk\""
  comment = "for bluesky domain"
  proxied = false
  ttl     = 1
}

resource "cloudflare_record" "dmarc" {
  zone_id = local.zone_id
  name    = "_dmarc"
  type    = "TXT"
  content = "\"v=DMARC1;  p=reject; rua=mailto:c92296529a26421b8dbb073791bb69d4@dmarc-reports.cloudflare.net\""
  proxied = false
  ttl     = 1
}

resource "cloudflare_record" "spf" {
  zone_id = local.zone_id
  name    = local.zone_name
  type    = "TXT"
  content = "\"v=spf1 include:icloud.com ~all\""
  proxied = false
  ttl     = 3600
}

resource "cloudflare_record" "apple_domain" {
  zone_id = local.zone_id
  name    = local.zone_name
  type    = "TXT"
  content = "\"apple-domain=lpnraAMlAhKshlvj\""
  proxied = false
  ttl     = 3600
}

resource "cloudflare_record" "google_site_verification" {
  zone_id = local.zone_id
  name    = local.zone_name
  type    = "TXT"
  content = "\"google-site-verification=o2s0lNQ-10v7zV-UMJDRa3wszc6ZQP6nRNtl_mM4y9U\""
  proxied = false
  ttl     = 3600
}
