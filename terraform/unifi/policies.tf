resource "unifi_firewall_policy" "yorha_to_bunker" {
  name                 = "YoRHa to Bunker"
  action               = "ALLOW"
  protocol             = "all"
  ip_version           = "BOTH"
  create_allow_respond = true

  source = {
    zone_id         = unifi_firewall_zone.yorha.id
    matching_target = "ANY"
  }

  destination = {
    zone_id         = unifi_firewall_zone.bunker.id
    matching_target = "ANY"
  }
}

resource "unifi_firewall_policy" "bunker_to_yorha" {
  name                  = "Bunker to YoRHa"
  action                = "BLOCK"
  protocol              = "all"
  ip_version            = "BOTH"
  connection_state_type = "CUSTOM"
  connection_states     = ["NEW"]
  logging               = true

  source = {
    zone_id         = unifi_firewall_zone.bunker.id
    matching_target = "ANY"
  }

  destination = {
    zone_id         = unifi_firewall_zone.yorha.id
    matching_target = "ANY"
  }
}

resource "unifi_firewall_policy" "yorha_to_lunar_tear" {
  name                 = "YoRHa to Lunar Tear"
  action               = "ALLOW"
  protocol             = "all"
  ip_version           = "BOTH"
  create_allow_respond = true

  source = {
    zone_id         = unifi_firewall_zone.yorha.id
    matching_target = "ANY"
  }

  destination = {
    zone_id         = unifi_firewall_zone.lunar_tear.id
    matching_target = "ANY"
  }
}

resource "unifi_firewall_policy" "yorha_to_scanners" {
  name                 = "YoRHa to Scanners"
  action               = "ALLOW"
  protocol             = "all"
  ip_version           = "BOTH"
  create_allow_respond = true

  source = {
    zone_id         = unifi_firewall_zone.yorha.id
    matching_target = "ANY"
  }

  destination = {
    zone_id         = unifi_firewall_zone.scanners.id
    matching_target = "ANY"
  }
}

resource "unifi_firewall_policy" "yorha_to_the_village" {
  name                 = "YoRHa to The Village"
  action               = "ALLOW"
  protocol             = "all"
  ip_version           = "BOTH"
  create_allow_respond = true

  source = {
    zone_id         = unifi_firewall_zone.yorha.id
    matching_target = "ANY"
  }

  destination = {
    zone_id         = unifi_firewall_zone.the_village.id
    matching_target = "ANY"
  }
}

resource "unifi_firewall_policy" "lunar_tear_to_scanners" {
  name                 = "Lunar Tear to Scanners"
  action               = "ALLOW"
  protocol             = "all"
  ip_version           = "BOTH"
  create_allow_respond = true

  source = {
    zone_id         = unifi_firewall_zone.lunar_tear.id
    matching_target = "ANY"
  }

  destination = {
    zone_id         = unifi_firewall_zone.scanners.id
    matching_target = "ANY"
  }
}
