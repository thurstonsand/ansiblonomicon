# Unattended machines keep their node keys; an expiry would drop them off the tailnet with
# nobody there to log in again.
data "tailscale_device" "server" {
  for_each = toset(["pod042", "pod153", "pod042-kvm"])

  name = "${each.key}.tail5f024.ts.net"
}

resource "tailscale_device_key" "server" {
  for_each = data.tailscale_device.server

  device_id           = each.value.node_id
  key_expiry_disabled = true
}

# Emergency access into Bunker, Lunar Tear, Scanners, and The Village; YoRHa stays out.
resource "tailscale_device_subnet_routes" "pod042_kvm" {
  device_id = data.tailscale_device.server["pod042-kvm"].node_id
  routes = [
    "10.10.10.0/24",
    "10.10.30.0/24",
    "10.10.40.0/24",
    "10.10.50.0/24",
  ]
}
