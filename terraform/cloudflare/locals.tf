locals {
  account_id = "f052696250a2530e9afce0df33177b65"
  zone_id    = "8fc4749bbd77ca905c380e48d62e24a2"

  zone_name = "thurstons.house"
  team_name = "thurstonshouse"

  tunnel_cname_target = "${cloudflare_tunnel.home.id}.cfargotunnel.com"

  home_ip = sensitive(cloudflare_record.storj.content)

  # Apps exposed via Cloudflare Tunnel - single source of truth for DNS + tunnel ingress
  tunnel_apps = [
    { host = "overseerr", service = "http://192.168.5.227:5055" },
    { host = "podsync", service = "http://192.168.5.228:80" },
    { host = "anypod", service = "http://192.168.5.231:8024" },
    { host = "blog", service = "http://192.168.5.233:2368" },
    { host = "cli-proxy-api", service = "http://192.168.5.235:8317" },
    { host = "clawdbot", service = "http://192.168.1.90:18789" },
    { host = "gmail-pubsub", service = "http://192.168.1.90:8788" },
  ]
}
