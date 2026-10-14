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

resource "unifi_port_profile" "pod042" {
  name = "pod042"
  # Every client VLAN is tagged here so pod042 can observe each segment from the
  # probe namespace, which is the only place those tags terminate. The host itself
  # holds no address on them. The controller expresses "every VLAN tagged" as
  # forward "all", and rewrites "customize" to it, so say it directly.
  forward               = "all"
  setting_preference    = "manual"
  native_networkconf_id = unifi_network.bunker.id
  tagged_vlan_mgmt      = "auto"
}

resource "unifi_device" "udmp" {
  mac               = "e4:38:83:1a:a0:45"
  name              = "UDM Pro"
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

# Outlet state is computed-only by design (see docs/designs/23-unifi-provider-fork.md,
# decision 6): no apply can move a relay. Outlets 5 and 7 power the Pro Max 24 PoE and
# the UDM Pro, so their state is asserted rather than declared.
resource "unifi_device" "power_distribution_pro" {
  mac               = "d8:b3:70:2c:b7:45"
  name              = "USP PDU Pro"
  allow_adoption    = true
  forget_on_destroy = false

  lifecycle {
    prevent_destroy = true

    postcondition {
      condition = length([
        for o in self.outlet_overrides : o
        if contains([5, 7], o.index) && o.relay_state
      ]) == 2
      error_message = "PDU outlets 5 (Pro Max 24 PoE) and 7 (UDM Pro) must both report relay_state = true."
    }
  }
}

# Outlet names cannot be declared, only observed. Warnings keep lost labels visible
# without blocking unrelated applies; restore them in the controller UI.
check "pdu_outlet_names" {
  assert {
    condition = one([
      for o in unifi_device.power_distribution_pro.outlet_overrides : o.name
      if o.index == 1
    ]) == "Hue Bridge Pro"
    error_message = "PDU USB outlet 1 should be named \"Hue Bridge Pro\"; it powers the bridge on switch port 2."
  }

  assert {
    condition = one([
      for o in unifi_device.power_distribution_pro.outlet_overrides : o.name
      if o.index == 5
    ]) == "USW Pro Max 24 PoE"
    error_message = "PDU outlet 5 should be named \"USW Pro Max 24 PoE\"."
  }

  assert {
    condition = one([
      for o in unifi_device.power_distribution_pro.outlet_overrides : o.name
      if o.index == 7
    ]) == "UDM Pro"
    error_message = "PDU outlet 7 should be named \"UDM Pro\"."
  }
}

# Both APs hold fixed, non-overlapping channels: 80 MHz on 5 GHz in the two
# non-DFS blocks (36-48 and 149-161), and 1 and 6 on 2.4 GHz. 2.4 GHz runs at
# medium power so dual-band clients prefer 5 GHz. The 6 GHz radio carries no
# SSID and keeps the controller's choice, but is declared because radio_table
# replaces the whole list.
resource "unifi_device" "u7_pro_max" {
  mac               = "94:2a:6f:2c:f0:d2"
  name              = "U7 Pro Max"
  allow_adoption    = true
  forget_on_destroy = false

  radio_table = [
    {
      radio         = "ng"
      channel       = "6"
      ht            = 20
      tx_power_mode = "medium"
    },
    {
      radio         = "na"
      channel       = "36"
      ht            = 80
      tx_power_mode = "high"
    },
    {
      radio   = "6e"
      channel = "auto"
      ht      = 160
    },
  ]

  lifecycle {
    prevent_destroy = true
  }
}

resource "unifi_device" "u7_pro_max_central" {
  mac               = "94:2a:6f:2c:cb:25"
  name              = "U7 Pro Max Central"
  allow_adoption    = true
  forget_on_destroy = false

  radio_table = [
    {
      radio         = "ng"
      channel       = "1"
      ht            = 20
      tx_power_mode = "medium"
    },
    {
      radio         = "na"
      channel       = "149"
      ht            = 80
      tx_power_mode = "high"
    },
    {
      radio   = "6e"
      channel = "auto"
      ht      = 160
    },
  ]

  lifecycle {
    prevent_destroy = true
  }
}

resource "unifi_device" "pro_max_24_poe" {
  mac               = "f4:e2:c6:ab:91:02"
  name              = "USW Pro Max 24 PoE"
  allow_adoption    = true
  forget_on_destroy = false

  port_override {
    index           = 1
    name            = "pod042-kvm"
    poe_mode        = "auto"
    port_profile_id = unifi_port_profile.bunker_access.id
  }

  port_override {
    index           = 2
    name            = "Hue Bridge Pro"
    poe_mode        = "off"
    port_profile_id = unifi_port_profile.scanners_access.id
  }

  port_override {
    index           = 3
    name            = "SuperLink Gateway"
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
    index           = 17
    name            = "pod042"
    poe_mode        = "auto"
    port_profile_id = unifi_port_profile.pod042.id
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
