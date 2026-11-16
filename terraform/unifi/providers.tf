provider "unifi" {
  api_key        = var.unifi_api_key
  api_url        = var.unifi_api_url
  allow_insecure = true
}
