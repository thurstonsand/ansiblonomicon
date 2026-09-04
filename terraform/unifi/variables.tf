variable "unifi_username" {
  type      = string
  sensitive = true
}

variable "unifi_password" {
  type      = string
  sensitive = true
}

variable "unifi_api_url" {
  type    = string
  default = "https://10.10.20.1"
}

variable "yorha_passphrase" {
  type      = string
  sensitive = true
}

variable "lunar_tear_passphrase" {
  type      = string
  sensitive = true
}

variable "the_village_passphrase" {
  type      = string
  sensitive = true
}

variable "scanners_passphrase" {
  type      = string
  sensitive = true
}
