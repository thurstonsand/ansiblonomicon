resource "unifi_wan" "was_110" {
  name         = "WAS-110"
  networkgroup = "WAN2"
  type         = "dhcp"
  enabled      = true

  mac_override         = var.unifi_wan_mac_override
  mac_override_enabled = true

  load_balance = {
    type              = "weighted"
    failover_priority = 1
  }
}

resource "unifi_wan" "internet_1" {
  name         = "Internet 1"
  networkgroup = "WAN"
  type         = "dhcp"
  enabled      = false

  mac_override_enabled = false

  load_balance = {
    type              = "failover-only"
    failover_priority = 2
  }
}
