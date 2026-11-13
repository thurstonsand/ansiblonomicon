resource "cloudflare_zero_trust_access_identity_provider" "onetimepin" {
  account_id = local.account_id
  name       = "One-Time PIN"
  type       = "onetimepin"
  config     = {}
}

resource "cloudflare_zero_trust_access_identity_provider" "google" {
  account_id = local.account_id
  name       = "Google SSO"
  type       = "google"

  config = {
    client_id    = "596354245524-oickjebe7bou2jofa2vnjkf4gcnagubs.apps.googleusercontent.com"
    pkce_enabled = true
    # The OAuth client's secret lives only in Cloudflare until the provider can write it without
    # keeping it in state.
    client_secret = "placeholder"
  }

  lifecycle {
    ignore_changes = [config.client_secret]
  }
}

resource "cloudflare_zero_trust_access_service_token" "onepassword" {
  account_id = local.account_id
  name       = "1Password"
  duration   = "forever"
}
