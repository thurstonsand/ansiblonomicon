resource "unifi_network" "bunker" {
  name                = "Bunker"
  purpose             = "corporate"
  subnet              = "10.10.10.1/24"
  auto_scale          = false
  setting_preference  = "manual"
  ipv6_interface_type = "none"
  multicast_dns       = false

  dhcp_server = {
    enabled = true
    start   = "10.10.10.100"
    stop    = "10.10.10.249"
  }

  lifecycle {
    prevent_destroy = true
  }
}

resource "unifi_network" "yorha" {
  name                = "YoRHa"
  purpose             = "corporate"
  vlan                = 20
  subnet              = "10.10.20.1/24"
  auto_scale          = false
  setting_preference  = "manual"
  ipv6_interface_type = "none"
  multicast_dns       = true

  dhcp_server = {
    enabled = true
    start   = "10.10.20.100"
    stop    = "10.10.20.249"
  }

  lifecycle {
    prevent_destroy = true
  }
}

resource "unifi_network" "lunar_tear" {
  name                = "Lunar Tear"
  purpose             = "corporate"
  vlan                = 30
  subnet              = "10.10.30.1/24"
  auto_scale          = false
  setting_preference  = "manual"
  ipv6_interface_type = "none"
  multicast_dns       = true

  dhcp_server = {
    enabled = true
    start   = "10.10.30.100"
    stop    = "10.10.30.249"
  }

  lifecycle {
    prevent_destroy = true
  }
}

resource "unifi_network" "scanners" {
  name                = "Scanners"
  purpose             = "corporate"
  vlan                = 40
  subnet              = "10.10.40.1/24"
  auto_scale          = false
  setting_preference  = "manual"
  ipv6_interface_type = "none"
  multicast_dns       = true

  dhcp_server = {
    enabled = true
    start   = "10.10.40.100"
    stop    = "10.10.40.249"
  }

  lifecycle {
    prevent_destroy = true
  }
}

resource "unifi_network" "the_village" {
  name                = "The Village"
  purpose             = "corporate"
  vlan                = 50
  subnet              = "10.10.50.1/24"
  auto_scale          = false
  setting_preference  = "manual"
  ipv6_interface_type = "none"
  multicast_dns       = false

  dhcp_server = {
    enabled = true
    start   = "10.10.50.100"
    stop    = "10.10.50.249"
  }

  lifecycle {
    prevent_destroy = true
  }
}
