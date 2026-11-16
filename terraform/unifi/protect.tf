resource "unifi_protect_sensor" "main_closet_motion" {
  mac                = "90:41:b2:2e:46:2e"
  name               = "Main Closet Motion Sensor"
  motion_enabled     = true
  motion_sensitivity = 100
}

resource "unifi_protect_sensor" "main_floor_smoke" {
  mac  = "a4:f8:ff:5a:6b:56"
  name = "Main Floor Smoke Detector"
}

resource "unifi_protect_sensor" "second_floor_smoke" {
  mac  = "a4:f8:ff:5a:5e:9c"
  name = "Second Floor Smoke Detector"
}
