resource "unifi_firewall_zone" "bunker" {
  name        = "Bunker"
  network_ids = [unifi_network.bunker.id]

  lifecycle {
    prevent_destroy = true
  }
}

resource "unifi_firewall_zone" "yorha" {
  name        = "YoRHa"
  network_ids = [unifi_network.yorha.id]

  lifecycle {
    prevent_destroy = true
  }
}

resource "unifi_firewall_zone" "lunar_tear" {
  name        = "Lunar Tear"
  network_ids = [unifi_network.lunar_tear.id]

  lifecycle {
    prevent_destroy = true
  }
}

resource "unifi_firewall_zone" "scanners" {
  name        = "Scanners"
  network_ids = [unifi_network.scanners.id]

  lifecycle {
    prevent_destroy = true
  }
}

resource "unifi_firewall_zone" "the_village" {
  name        = "The Village"
  network_ids = [unifi_network.the_village.id]

  lifecycle {
    prevent_destroy = true
  }
}
