locals {
  account_id = "f052696250a2530e9afce0df33177b65"
  zone_id    = "8fc4749bbd77ca905c380e48d62e24a2"

  zone_name = "thurstons.house"
  team_name = "thurstonshouse"

  tunnel_cname_target = "${cloudflare_tunnel.home.id}.cfargotunnel.com"

  home_ip = sensitive(cloudflare_record.storj.content)

  # Apps exposed via Cloudflare Tunnel - single source of truth for DNS + tunnel ingress
  tunnel_apps = [
    { host = "seerr", service = "http://caddy:80" },
    { host = "anypod", service = "http://caddy:80" },
    { host = "blog", service = "http://caddy:80" },
    { host = "cli-proxy-api", service = "http://caddy:80" },
  ]

  internal_tunnel_apps = [
    { host = "pod042-kvm", service = "https://10.10.10.34", no_tls_verify = true },
  ]

  # SSH endpoints exposed through Cloudflare Access.
  ssh_tunnel_apps = [
    { host = "haos-ssh", ip = "192.168.1.89", port = 22222 },
    { host = "udmp-ssh", ip = "192.168.1.1", port = 22 },
  ]

  recovery_ssh_tunnel_apps = [
    { host = "pod042-ssh", ip = "10.10.10.42", port = 22 },
    { host = "pod042-kvm-ssh", ip = "10.10.10.34", port = 22 },
  ]

  # Public HTTPS hosts that should advertise host-scoped HSTS.
  # Intentionally omit DNS-only / externally hosted records (for example ha.* via Nabu Casa)
  # and omit includeSubDomains so sibling hosts can remain plain HTTP internally if needed.
  hsts_hosts = [
    local.zone_name,
    "www.${local.zone_name}",
    "blog.${local.zone_name}",
    "overseerr.${local.zone_name}",
    "seerr.${local.zone_name}",
    "anypod.${local.zone_name}",
    "cli-proxy-api.${local.zone_name}",
    "aig.${local.zone_name}",
  ]
}
