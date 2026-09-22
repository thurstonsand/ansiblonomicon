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
      # Untrusted vendor hardware lives on The Village, but Home Assistant sits on
      # Scanners, and HomeKit accessories are resolved through mDNS on every
      # reconnect rather than only at pairing. Without reflection the thermostats
      # are reachable exactly until they renumber. Reflection is mutual and
      # discovery-only: The Village can now see the reflected service records from
      # the other segments, but no policy permits it to open a connection to them.
      unifi_network.the_village.id,
    ]
    predefined_services = [
      "apple_airPlay",
      "homeKit",
    ]
    custom_services = [
      {
        name    = "AirPrint"
        address = "_ipp._tcp.local"
      },
      # iOS browses _ipp._tcp,_universal rather than plain _ipp._tcp, so the printer's
      # AirPrint record is invisible to a phone unless the subtype crosses too.
      {
        name    = "AirPrint Universal"
        address = "_universal._sub._ipp._tcp.local"
      },
      {
        name    = "AirPrint Secure"
        address = "_ipps._tcp.local"
      },
      {
        name    = "AirScan"
        address = "_uscan._tcp.local"
      },
      {
        name    = "AirScan Secure"
        address = "_uscans._tcp.local"
      },
      {
        name    = "Philips Hue"
        address = "_hue._tcp.local"
      },
      {
        name    = "HomeKit Accessory"
        address = "_hap._tcp.local"
      },
    ]
  }
}
