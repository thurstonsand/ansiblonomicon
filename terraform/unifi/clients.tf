resource "unifi_client" "eight_sleep_pod_5" {
  mac            = "70:b6:51:01:be:51"
  name           = "Eight Sleep Pod 5"
  allow_existing = true
}

resource "unifi_client" "nausea" {
  mac            = "4c:fc:aa:6d:41:2a"
  name           = "Nausea - Tesla Model 3"
  allow_existing = true
}

resource "unifi_client" "kitchen_homepod" {
  mac            = "ac:bc:b5:ca:34:ab"
  name           = "Apple HomePod - Kitchen"
  allow_existing = true
}

resource "unifi_client" "pod042_kvm" {
  mac              = "94:83:c4:c0:d7:7b"
  name             = "pod042-kvm"
  fixed_ip         = "10.10.10.34"
  local_dns_record = "pod042-kvm"
  allow_existing   = true
}
