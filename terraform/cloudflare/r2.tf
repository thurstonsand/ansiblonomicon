# R2 bucket for Terraform state storage
resource "cloudflare_r2_bucket" "tfstate" {
  account_id = local.account_id
  name       = "tfstate"
  location   = "ENAM" # Eastern North America
}

# Restic repository for loch-highland-atlas backups
resource "cloudflare_r2_bucket" "loch_highland_atlas_backups" {
  account_id = local.account_id
  name       = "loch-highland-atlas-backups"
  location   = "ENAM"
}
