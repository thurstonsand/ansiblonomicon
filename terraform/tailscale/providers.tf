# Authenticates with the "1Password" OAuth client (all scopes) from TAILSCALE_OAUTH_CLIENT_ID
# and TAILSCALE_OAUTH_CLIENT_SECRET. It is created by hand and never managed here, so no apply
# can revoke the credential running it.
provider "tailscale" {}
