# Amp orbs mint their own tag:amp-orb auth keys with this client; its secret lives in 1Password.
resource "tailscale_oauth_client" "amp_orb" {
  description = "amp-orb"
  scopes      = ["auth_keys"]
  tags        = ["tag:amp-orb"]
}
