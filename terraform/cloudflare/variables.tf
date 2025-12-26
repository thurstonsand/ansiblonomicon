variable "cloudflare_api_token" {
  description = "Cloudflare API token"
  type        = string
  sensitive   = true
}

variable "parent_home_ip" {
  description = "Parents' home IP address for Zero Trust bypass"
  type        = string
  sensitive   = true
}
