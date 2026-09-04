resource "unifi_static_route" "was_110_lct" {
  name           = "WAS-110 LCT"
  type           = "interface-route"
  network        = "192.168.11.0/24"
  interface      = unifi_wan.was_110.id
  gateway_device = unifi_device.udmp.mac
  distance       = 1

  lifecycle {
    prevent_destroy = true
  }
}
