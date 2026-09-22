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
  # AWDL, which carries Continuity, only runs on 2.4 and 5 GHz. A Mac parked on
  # 6 GHz cannot discover an iPhone associated to the same SSID on 5 GHz, and
  # macOS reports it as "not on the same network".
  wlan_bands = ["2g", "5g"]
  # MLO splits the SSID into an MLD BSS and a legacy one. Clients on the legacy
  # side, which here is every device except the iPhone, then receive no
  # group-addressed traffic at all: no reflected mDNS, and nothing from each
  # other. Discovery across VLANs cannot work while that is true. Worth retesting
  # once more than one device here speaks Wi-Fi 7, with a 30-second capture of
  # udp/5353 on a legacy-side client as the verdict.
  mlo_enabled = false

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
  name          = "Scanners"
  security      = "wpapsk"
  passphrase    = var.scanners_passphrase
  network_id    = unifi_network.scanners.id
  ap_group_mode = "all"
  user_group_id = data.unifi_client_qos_rate.default.id
  # On WPA3 transition the Canon answered unicast normally and ignored every
  # broadcast and multicast frame, so it served IPP and the Canon app while being
  # invisible to any discovery browse. It started answering seconds after this
  # became plain WPA2. Its reception still lapses at times, which is unexplained,
  # but it announces itself unprompted often enough for the gateway to cache it.
  wpa3_support    = false
  wpa3_transition = false
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
