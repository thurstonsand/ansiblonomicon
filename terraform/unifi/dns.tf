locals {
  pod042_service_dns_names = toset([
    "anypod.thurstons.house",
    "blog.thurstons.house",
    "cli-proxy-api.thurstons.house",
    "dash.thurstons.house",
    "netdata.thurstons.house",
    "neutarr.thurstons.house",
    "plex.thurstons.house",
    "pod042.thurstons.house",
    "prowlarr.thurstons.house",
    "radarr.thurstons.house",
    "scrypted.thurstons.house",
    "seerr.thurstons.house",
    "sonarr.thurstons.house",
    "thurstons.house",
    "torrent.thurstons.house",
    "www.thurstons.house",
  ])
}

resource "unifi_dns_record" "pod042_service" {
  for_each = local.pod042_service_dns_names

  name        = each.value
  record_type = "A"
  value       = unifi_client.pod042.fixed_ip
  enabled     = true
  ttl         = "5m"
}

resource "unifi_dns_record" "kvm" {
  name        = "kvm.thurstons.house"
  record_type = "A"
  value       = unifi_client.pod042_kvm.fixed_ip
  enabled     = true
  ttl         = "5m"
}
