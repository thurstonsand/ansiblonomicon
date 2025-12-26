resource "cloudflare_zero_trust_access_identity_provider" "onetimepin" {
  account_id = local.account_id
  name       = "One-Time PIN"
  type       = "onetimepin"
}

resource "cloudflare_zero_trust_access_identity_provider" "google" {
  account_id = local.account_id
  name       = "Google SSO"
  type       = "google"

  config {
    client_id     = "placeholder"
    client_secret = "placeholder"
  }

  lifecycle {
    ignore_changes = [config]
  }
}

resource "cloudflare_zero_trust_access_service_token" "onepassword" {
  account_id = local.account_id
  name       = "1Password"
}
