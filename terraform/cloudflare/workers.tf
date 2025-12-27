# LLM API Worker - validates API key before forwarding to cli-proxy-api
#
# llms.thurstons.house → Worker (API key auth) → cli-proxy-api tunnel
# cli-proxy-api.thurstons.house → Cloudflare Access (browser auth) → tunnel

resource "cloudflare_workers_script" "cli_proxy_api" {
  account_id = local.account_id
  name       = "cli-proxy-api"
  content    = file("${path.module}/workers/cli-proxy-api/worker.js")
  module     = true

  plain_text_binding {
    name = "ORIGIN_HOSTNAME"
    text = "cli-proxy-api.${local.zone_name}"
  }

  plain_text_binding {
    name = "DEBUG"
    text = "false"
  }
}

resource "cloudflare_workers_route" "cli_proxy_api" {
  zone_id     = local.zone_id
  pattern     = "llms.${local.zone_name}/*"
  script_name = cloudflare_workers_script.cli_proxy_api.name
}

# DNS record for the Worker endpoint
resource "cloudflare_record" "llms" {
  zone_id = local.zone_id
  name    = "llms"
  type    = "AAAA"
  content = "100::"
  proxied = true
  ttl     = 1
  comment = "Worker-only endpoint for API key auth"
}
