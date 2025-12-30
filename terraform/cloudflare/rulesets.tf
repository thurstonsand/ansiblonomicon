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
      # Skip SBFM (Super Bot Fight Mode) phase for AI Gateway callbacks
      phases = ["http_request_sbfm"]
    }
    description = "allow llm clients on llms api (skip security for AI Gateway)"
    enabled     = true
    expression  = "(http.host in {\"llms.thurstons.house\" \"aig.thurstons.house\" \"cli-proxy-api.thurstons.house\"}) and ((http.user_agent contains \"OpenAI\") or (http.user_agent contains \"llm/\"))"
    logging {
      enabled = true
    }
  }
}

resource "cloudflare_ruleset" "hsts" {
  kind    = "zone"
  name    = "default"
  phase   = "http_request_late_transform"
  zone_id = local.zone_id
  rules {
    action = "rewrite"
    action_parameters {
      headers {
        name      = "Strict-Transport-Security"
        operation = "set"
        value     = "max-age=31536000; preload"
      }
      headers {
        name      = "X-Content-Type-Options"
        operation = "set"
        value     = "nosniff"
      }
    }
    description = "HSTS with mixed"
    enabled     = true
    expression  = "(not http.host contains \"status\")"
  }
}
