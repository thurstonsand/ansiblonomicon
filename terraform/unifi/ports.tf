resource "unifi_port_profile" "bunker_access" {
  name                  = "Bunker Access"
  forward               = "native"
  setting_preference    = "manual"
  native_networkconf_id = unifi_network.bunker.id
  tagged_vlan_mgmt      = "block_all"
}

resource "unifi_port_profile" "yorha_access" {
  name                  = "YoRHa Access"
  forward               = "native"
  setting_preference    = "manual"
  native_networkconf_id = unifi_network.yorha.id
  tagged_vlan_mgmt      = "block_all"
}

resource "unifi_port_profile" "scanners_access" {
  name                  = "Scanners Access"
  forward               = "native"
  setting_preference    = "manual"
  native_networkconf_id = unifi_network.scanners.id
  tagged_vlan_mgmt      = "block_all"
}

resource "unifi_port_profile" "the_village_access" {
  name                  = "The Village Access"
  forward               = "native"
  setting_preference    = "manual"
  native_networkconf_id = unifi_network.the_village.id
  tagged_vlan_mgmt      = "block_all"
}

resource "unifi_port_profile" "infrastructure_trunk" {
  name                  = "Infrastructure Trunk"
  forward               = "all"
  setting_preference    = "manual"
  native_networkconf_id = unifi_network.bunker.id
  tagged_vlan_mgmt      = "auto"
}

resource "unifi_device" "udmp" {
  mac               = "e4:38:83:1a:a0:45"
  forget_on_destroy = false

  ethernet_override {
    ifname        = "eth8"
    network_group = "WAN"
  }

  ethernet_override {
    ifname        = "eth9"
    network_group = "WAN2"
  }

  port_override {
    index           = 1
    name            = "Bunker recovery"
    port_profile_id = unifi_port_profile.bunker_access.id
  }

  port_override {
    index           = 2
    name            = "YoRHa test"
    port_profile_id = unifi_port_profile.yorha_access.id
  }

  port_override {
    index           = 7
    name            = "Power Distribution Pro"
    port_profile_id = unifi_port_profile.bunker_access.id
  }

  lifecycle {
    prevent_destroy = true
  }
}

resource "unifi_device" "power_distribution_pro" {
  mac               = "d8:b3:70:2c:b7:45"
  allow_adoption    = true
  forget_on_destroy = false

  lifecycle {
    prevent_destroy = true
  }
}

resource "unifi_device" "u7_pro_max" {
  mac               = "94:2a:6f:2c:f0:d2"
  allow_adoption    = true
  forget_on_destroy = false

  lifecycle {
    prevent_destroy = true
  }
}

resource "unifi_device" "pro_max_24_poe" {
  mac               = "f4:e2:c6:ab:91:02"
  allow_adoption    = true
  forget_on_destroy = false

  port_override {
    index           = 1
    name            = "pod042-kvm"
    poe_mode        = "auto"
    port_profile_id = unifi_port_profile.bunker_access.id
  }

  port_override {
    index           = 23
    name            = "U7 Pro Max bootstrap"
    poe_mode        = "auto"
    port_profile_id = unifi_port_profile.infrastructure_trunk.id
  }

  port_override {
    index           = 24
    name            = "Bunker access"
    poe_mode        = "auto"
    port_profile_id = unifi_port_profile.bunker_access.id
  }

  port_override {
    index           = 26
    name            = "UDM Pro uplink"
    port_profile_id = unifi_port_profile.infrastructure_trunk.id
  }

  lifecycle {
    prevent_destroy = true
  }
}
