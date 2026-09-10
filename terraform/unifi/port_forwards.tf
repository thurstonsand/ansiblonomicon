resource "unifi_port_forward" "plex" {
  name     = "Plex"
  protocol = "tcp"

  wan = {
    interface  = "wan2"
    ip_address = "any"
    port       = "32400"
  }

  forward = {
    ip   = "10.10.10.42"
    port = "32400"
  }
}
