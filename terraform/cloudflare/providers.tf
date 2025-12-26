provider "cloudflare" {
  api_token = var.cloudflare_api_token

  # Rate limiting configuration
  rps = 2
  retries     = 5
  min_backoff = 5
  max_backoff = 60
}
