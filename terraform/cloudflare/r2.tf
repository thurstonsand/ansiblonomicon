# R2 bucket for Terraform state storage
resource "cloudflare_r2_bucket" "tfstate" {
  account_id = local.account_id
  name       = "tfstate"
  location   = "ENAM" # Eastern North America
}
