# One-time moves from provider v4 resource types; delete this file once the v5 apply has run.

moved {
  from = cloudflare_record.storj
  to   = cloudflare_dns_record.home_ip
}

moved {
  from = cloudflare_record.acme_challenge_ha
  to   = cloudflare_dns_record.acme_challenge_ha
}

moved {
  from = cloudflare_record.ha
  to   = cloudflare_dns_record.ha
}

moved {
  from = cloudflare_record.screenshot
  to   = cloudflare_dns_record.screenshot
}

moved {
  from = cloudflare_record.sig1_domainkey
  to   = cloudflare_dns_record.sig1_domainkey
}

moved {
  from = cloudflare_record.root
  to   = cloudflare_dns_record.root
}

moved {
  from = cloudflare_record.amp_subdomain
  to   = cloudflare_dns_record.amp_subdomain
}

moved {
  from = cloudflare_record.amp_subdomain_wildcard
  to   = cloudflare_dns_record.amp_subdomain_wildcard
}

moved {
  from = cloudflare_record.amp_subdomain_certificate
  to   = cloudflare_dns_record.amp_subdomain_certificate
}

moved {
  from = cloudflare_record.www
  to   = cloudflare_dns_record.www
}

moved {
  from = cloudflare_record.overseerr_redirect
  to   = cloudflare_dns_record.overseerr_redirect
}

moved {
  from = cloudflare_record.mx1
  to   = cloudflare_dns_record.mx1
}

moved {
  from = cloudflare_record.mx2
  to   = cloudflare_dns_record.mx2
}

moved {
  from = cloudflare_record.atproto_its
  to   = cloudflare_dns_record.atproto_its
}

moved {
  from = cloudflare_record.amp_subdomain_verification
  to   = cloudflare_dns_record.amp_subdomain_verification
}

moved {
  from = cloudflare_record.dmarc
  to   = cloudflare_dns_record.dmarc
}

moved {
  from = cloudflare_record.spf
  to   = cloudflare_dns_record.spf
}

moved {
  from = cloudflare_record.apple_domain
  to   = cloudflare_dns_record.apple_domain
}

moved {
  from = cloudflare_record.google_site_verification
  to   = cloudflare_dns_record.google_site_verification
}

moved {
  from = cloudflare_record.snippethost
  to   = cloudflare_dns_record.snippethost
}

moved {
  from = cloudflare_record.snippethost_gitlab_verification
  to   = cloudflare_dns_record.snippethost_gitlab_verification
}

moved {
  from = cloudflare_record.tesla
  to   = cloudflare_dns_record.tesla
}

moved {
  from = cloudflare_record.pod153_mcp
  to   = cloudflare_dns_record.pod153_mcp
}

moved {
  from = cloudflare_record.nurb
  to   = cloudflare_dns_record.nurb
}

moved {
  from = cloudflare_record.tunnel_app
  to   = cloudflare_dns_record.tunnel_app
}

moved {
  from = cloudflare_record.internal_tunnel_app
  to   = cloudflare_dns_record.internal_tunnel_app
}

moved {
  from = cloudflare_record.tunnel_ssh_app
  to   = cloudflare_dns_record.tunnel_ssh_app
}

moved {
  from = cloudflare_tunnel.home
  to   = cloudflare_zero_trust_tunnel_cloudflared.home
}

moved {
  from = cloudflare_tunnel_config.home
  to   = cloudflare_zero_trust_tunnel_cloudflared_config.home
}
