resource "cloudflare_ruleset" "firewall_custom" {
  kind    = "zone"
  name    = "default"
  phase   = "http_request_firewall_custom"
  zone_id = local.zone_id
  rules {
    action = "skip"
    action_parameters {
      phases   = ["http_ratelimit", "http_request_firewall_managed", "http_request_sbfm"]
      products = ["zoneLockdown", "uaBlock", "bic", "hot", "securityLevel", "rateLimit", "waf"]
      ruleset  = "current"
    }
    description = "allow pocket casts"
    enabled     = true
    expression  = "(http.host in {\"crawler1.pocketcasts.com\" \"crawler2.pocketcasts.com\"}) or (ip.src in $pocket_casts)"
    logging {
      enabled = true
    }
  }
  rules {
    action = "skip"
    action_parameters {
      # Skip SBFM and managed WAF for AI Gateway-related machine endpoints.
      phases = ["http_request_sbfm", "http_request_firewall_managed"]
    }
    description = "skip managed security on AI Gateway machine endpoints"
    enabled     = true
    expression  = "(http.host in {\"aig.thurstons.house\" \"cli-proxy-api.thurstons.house\" \"hooks.thurstons.house\" })"
    logging {
      enabled = true
    }
  }
}

resource "cloudflare_ruleset" "rate_limits" {
  kind    = "zone"
  name    = "default"
  phase   = "http_ratelimit"
  zone_id = local.zone_id

  rules {
    action = "block"
    ratelimit {
      characteristics     = ["cf.colo.id", "ip.src"]
      period              = 10
      requests_per_period = 10
      mitigation_timeout  = 10
    }
    description = "block on Seerr login bursts (free-plan fallback)"
    enabled     = true
    expression  = "(http.request.uri.path eq \"/login\")"
  }
}

resource "cloudflare_ruleset" "redirects" {
  kind    = "zone"
  name    = "redirects"
  phase   = "http_request_dynamic_redirect"
  zone_id = local.zone_id

  rules {
    ref         = "redirect_overseerr_to_seerr"
    action      = "redirect"
    description = "redirect Overseerr hostname to Seerr"
    enabled     = true
    expression  = "(http.host eq \"overseerr.${local.zone_name}\")"

    action_parameters {
      from_value {
        status_code           = 301
        preserve_query_string = true

        target_url {
          expression = "concat(\"https://seerr.${local.zone_name}\", http.request.uri.path)"
        }
      }
    }
  }
}

resource "cloudflare_ruleset" "response_headers" {
  kind    = "zone"
  name    = "default"
  phase   = "http_response_headers_transform"
  zone_id = local.zone_id

  rules {
    action = "rewrite"
    action_parameters {
      headers {
        name      = "Strict-Transport-Security"
        operation = "set"
        value     = "max-age=31536000"
      }
      headers {
        name      = "X-Content-Type-Options"
        operation = "set"
        value     = "nosniff"
      }
    }
    description = "host-scoped HSTS for public HTTPS hosts"
    enabled     = true
    expression  = format("(http.host in {%s})", join(" ", formatlist("\"%s\"", local.hsts_hosts)))
  }
}
