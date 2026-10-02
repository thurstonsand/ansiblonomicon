# Holds the OAuth client behind Cloudflare Access "Google SSO"; it needs no APIs.
resource "google_project" "cloudflare" {
  name       = "cloudflare"
  project_id = "cloudflare-331404"
}
