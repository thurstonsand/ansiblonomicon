resource "cloudflare_list" "pocket_casts" {
  account_id  = local.account_id
  description = "known ips for pocket casts"
  kind        = "ip"
  name        = "pocket_casts"

  item {
    value {
      ip = "3.219.254.95"
    }
  }
  item {
    value {
      ip = "35.169.190.168"
    }
  }
}
