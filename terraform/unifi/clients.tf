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

resource "unifi_client" "thurston_mbp" {
  mac            = "0a:e0:d0:07:0a:37"
  name           = "Thurston's M4 Pro MBP"
  allow_existing = true
}

resource "unifi_client" "thurston_iphone" {
  mac            = "16:15:12:57:9e:da"
  name           = "Thurston's iPhone Air"
  allow_existing = true
}

resource "unifi_client" "thurston_watch" {
  mac            = "4a:d0:ba:a0:44:54"
  name           = "Thurston's Apple Watch Series 10"
  allow_existing = true
}

# The Dell dual-boot presents a different address per partition. Only Omarchy's is
# burned-in; Windows randomizes, so it earns no record until it stops.
resource "unifi_client" "dell_omarchy" {
  mac            = "84:08:3a:61:fe:81"
  name           = "Dell Laptop - Omarchy"
  allow_existing = true
}

resource "unifi_client" "thurston_work_mbp" {
  mac            = "2e:01:55:27:9b:41"
  name           = "Thurston's Work MacBook"
  allow_existing = true
}

# Two Espressif boards nobody can identify. Their only traffic is NTP and one AWS IoT
# account that matches no other device here. Blocked to find out what stops working;
# flip these back to false the moment something does.
resource "unifi_client" "unidentified_espressif_d07c" {
  mac            = "3c:61:05:6a:d0:7c"
  name           = "Unidentified Espressif d0:7c"
  blocked        = true
  allow_existing = true
}

resource "unifi_client" "unidentified_espressif_3690" {
  mac            = "c8:c9:a3:c2:36:90"
  name           = "Unidentified Espressif 36:90"
  blocked        = true
  allow_existing = true
}

resource "unifi_client" "canon_printer" {
  mac            = "14:d4:24:f2:6f:e6"
  name           = "Canon MF654Cdw"
  fixed_ip       = "10.10.40.187"
  allow_existing = true
}

resource "unifi_client" "hue_bridge" {
  mac            = "c4:29:96:bb:7a:cd"
  name           = "Hue Bridge Pro"
  allow_existing = true
}

resource "unifi_client" "pod042_kvm" {
  mac              = "94:83:c4:c0:d7:7b"
  name             = "pod042-kvm"
  fixed_ip         = "10.10.10.34"
  local_dns_record = "pod042-kvm"
  allow_existing   = true
}

resource "unifi_client" "pod042" {
  mac              = "a0:36:bc:28:37:41"
  name             = "pod042"
  fixed_ip         = "10.10.10.42"
  local_dns_record = "pod042"
  allow_existing   = true
}

resource "unifi_client" "home_assistant" {
  mac              = "00:16:3e:48:41:42"
  name             = "home-assistant"
  fixed_ip         = "10.10.40.42"
  local_dns_record = "home-assistant"
  allow_existing   = true
}
