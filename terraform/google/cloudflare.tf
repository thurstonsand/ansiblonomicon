# Holds the Google sign-in clients: Cloudflare Access "Google SSO" and Comail on no9-type-s.
# Comail reaches Gmail over IMAP/SMTP with XOAUTH2, so the project needs no APIs.
# Google Auth Platform has no API, so these record what was set by hand:
# - Branding: app name "Cloudflare", shown on both clients' consent screens. Publishing requires
#   a home page and privacy policy; both point at github.com/NextOSP/comail, which keeps mail
#   on the machine, and github.com is the authorized domain.
# - Audience: External, In production and unverified, so Gmail refresh tokens outlive Testing's
#   seven days; Gmail sign-in clicks through Google's unverified-app warning.
# - Data access: https://mail.google.com/, the only scope Gmail's XOAUTH2 accepts.
# - Clients: "Comail" is a Desktop app client, the only type that accepts Comail's
#   http://127.0.0.1:<random port> loopback redirect. Its secret lives in 1Password
#   (agent vault, "Comail Client ID/Secret") and reaches Comail through fnox.omarchy.toml.
locals {
  comail_oauth_client_id = "596354245524-iefb1k1v2eb9u1po9u2ecddp1dfaijnc.apps.googleusercontent.com"
}

output "comail_oauth_client_id" {
  value = local.comail_oauth_client_id
}

resource "google_project" "cloudflare" {
  name       = "cloudflare"
  project_id = "cloudflare-331404"
}
