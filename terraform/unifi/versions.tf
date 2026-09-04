terraform {
  required_version = ">= 1.12.0"

  backend "s3" {
    bucket = "tfstate"
    key    = "unifi/terraform.tfstate"
    region = "auto"

    endpoints = {
      s3 = "https://f052696250a2530e9afce0df33177b65.r2.cloudflarestorage.com"
    }

    skip_credentials_validation = true
    skip_metadata_api_check     = true
    skip_region_validation      = true
    skip_requesting_account_id  = true
    skip_s3_checksum            = true
    use_lockfile                = true
    use_path_style              = true
  }

  required_providers {
    unifi = {
      source  = "github.com/thurstonsand/unifi"
      version = "0.56.0-ansiblonomicon.5"
    }
  }
}
