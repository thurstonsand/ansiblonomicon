resource "google_project" "maps" {
  name            = "Maps Essentials"
  project_id      = "ansiblonomicon-maps"
  billing_account = local.billing_account
}

resource "google_project_service" "maps" {
  for_each = toset([
    "apikeys.googleapis.com",
    "mapstools.googleapis.com",
  ])

  project = google_project.maps.project_id
  service = each.value
}

resource "google_apikeys_key" "maps" {
  project      = google_project.maps.project_id
  name         = "executor"
  display_name = "Executor Maps Essentials"

  restrictions {
    api_targets {
      service = "mapstools.googleapis.com"
    }
  }

  depends_on = [google_project_service.maps]
}

output "maps_api_key" {
  value     = google_apikeys_key.maps.key_string
  sensitive = true
}
