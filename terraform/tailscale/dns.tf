# Tailscale stores a NextDNS profile as its anycast IPv6 address and upgrades it to DoH on clients.
resource "tailscale_dns_configuration" "tailnet" {
  magic_dns          = false
  override_local_dns = true

  nameservers {
    address = "2a07:a8c0::${substr(var.nextdns_profile_id, 0, 2)}:${substr(var.nextdns_profile_id, 2, 4)}"
  }
}
