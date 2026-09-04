resource "unifi_setting" "site" {
  mgmt = {
    auto_upgrade      = true
    auto_upgrade_hour = 3
  }

  mdns = {
    mode        = "custom"
    enabled_for = "some"
    enabled_for_network_ids = [
      unifi_network.yorha.id,
      unifi_network.lunar_tear.id,
      unifi_network.scanners.id,
    ]
    predefined_services = [
      "apple_airPlay",
      "homeKit",
    ]
    custom_services = []
  }
}
