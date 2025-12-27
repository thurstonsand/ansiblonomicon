resource "cloudflare_ruleset" "cache_settings" {
  kind    = "zone"
  name    = "default"
  phase   = "http_request_cache_settings"
  zone_id = local.zone_id
  rules {
    action = "set_cache_settings"
    action_parameters {
      cache = false
    }
    description = "temp bypass for lemonade stand video"
    enabled     = true
    expression  = "(http.request.uri.path wildcard r\"/media/lemonade-stand-premium/142157724.mp4\") or (http.request.uri.path wildcard r\"/feeds/lemonade-stand-premium.xml\")"
  }
}

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
      phases   = ["http_ratelimit", "http_request_firewall_managed", "http_request_sbfm"]
      products = ["zoneLockdown", "uaBlock", "bic", "hot", "securityLevel", "rateLimit", "waf"]
      ruleset  = "current"
    }
    description = "allow openai sdk on llms api"
    enabled     = true
    expression  = "(http.host eq \"llms.thurstons.house\") and (http.user_agent contains \"OpenAI\")"
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
