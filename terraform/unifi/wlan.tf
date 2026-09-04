data "unifi_client_qos_rate" "default" {
  name = "Default"
}

resource "unifi_wlan" "yorha" {
  name            = "YoRHa"
  security        = "wpapsk"
  passphrase      = var.yorha_passphrase
  network_id      = unifi_network.yorha.id
  ap_group_mode   = "all"
  user_group_id   = data.unifi_client_qos_rate.default.id
  wpa3_support    = true
  wpa3_transition = false
  pmf_mode        = "required"
  wlan_bands      = ["2g", "5g", "6g"]
  mlo_enabled     = true

  lifecycle {
    ignore_changes = [ap_group_ids]
  }
}

resource "unifi_wlan" "lunar_tear" {
  name            = "Lunar Tear"
  security        = "wpapsk"
  passphrase      = var.lunar_tear_passphrase
  network_id      = unifi_network.lunar_tear.id
  ap_group_mode   = "all"
  user_group_id   = data.unifi_client_qos_rate.default.id
  wpa3_support    = true
  wpa3_transition = true
  pmf_mode        = "optional"
  wlan_bands      = ["2g", "5g"]

  lifecycle {
    ignore_changes = [ap_group_ids]
  }
}

resource "unifi_wlan" "scanners" {
  name            = "Scanners"
  security        = "wpapsk"
  passphrase      = var.scanners_passphrase
  network_id      = unifi_network.scanners.id
  ap_group_mode   = "all"
  user_group_id   = data.unifi_client_qos_rate.default.id
  wpa3_support    = true
  wpa3_transition = true
  pmf_mode        = "optional"
  wlan_bands      = ["2g", "5g"]

  lifecycle {
    ignore_changes = [ap_group_ids]
  }
}

resource "unifi_wlan" "the_village" {
  name            = "The Village"
  security        = "wpapsk"
  passphrase      = var.the_village_passphrase
  network_id      = unifi_network.the_village.id
  ap_group_mode   = "all"
  user_group_id   = data.unifi_client_qos_rate.default.id
  wpa3_support    = false
  wpa3_transition = false
  pmf_mode        = "optional"
  wlan_band       = "2g"
  wlan_bands      = ["2g"]

  lifecycle {
    ignore_changes = [ap_group_ids]
  }
}
