# LLM API Worker - validates API key before forwarding to backend
#
# llms.thurstons.house → Worker (API key auth) → cli-proxy-api tunnel
# cli-proxy-api.thurstons.house → Cloudflare Access (browser auth) → tunnel

resource "cloudflare_workers_script" "llms" {
  account_id = local.account_id
  name       = "llms"
  content    = file("${path.module}/workers/llms/worker.js")
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

resource "cloudflare_workers_route" "llms" {
  zone_id     = local.zone_id
  pattern     = "llms.${local.zone_name}/*"
  script_name = cloudflare_workers_script.llms.name
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
