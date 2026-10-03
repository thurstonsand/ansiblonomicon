# The Device Access project signs in with this project's OAuth client and publishes events
# to nest-events. Neither the Device Access console nor Google Auth Platform (branding,
# audience, OAuth clients) has an API, so these record what was set by hand.
# The 2021 project never exposed DoorbellChime for the 3rd-gen wired doorbell
# (https://issuetracker.google.com/issues/468317741); a fresh project in 2026 did.
locals {
  nest_device_access_project_id = "f89a7a86-a5a4-4a79-a43a-47dcff4e67d9"
  nest_oauth_client_id          = "349970122408-4e8fns65ve79hsf1sr2us0b1ncpkdn21.apps.googleusercontent.com"
}

output "nest_device_access_project_id" {
  value = local.nest_device_access_project_id
}

output "nest_oauth_client_id" {
  value = local.nest_oauth_client_id
}

resource "google_project" "nest" {
  name            = "Nest Bridge"
  project_id      = "nest-bridge-680545"
  billing_account = local.billing_account
}

resource "google_project_service" "nest_smart_device_management" {
  project = google_project.nest.project_id
  service = "smartdevicemanagement.googleapis.com"
}

resource "google_project_service" "nest_pubsub" {
  project = google_project.nest.project_id
  service = "pubsub.googleapis.com"
}

resource "google_pubsub_topic" "nest_events" {
  project = google_project.nest.project_id
  name    = "nest-events"

  depends_on = [google_project_service.nest_pubsub]
}

# Device Access publishes events as this Google-owned group.
resource "google_pubsub_topic_iam_member" "nest_events_sdm_publisher" {
  project = google_project.nest.project_id
  topic   = google_pubsub_topic.nest_events.name
  role    = "roles/pubsub.publisher"
  member  = "group:sdm-publisher@googlegroups.com"
}

# Secret path segment that Caddy on pod042 forwards to Scrypted's Google Device Access endpoint.
variable "nest_events_token" {
  type      = string
  sensitive = true
}

resource "google_pubsub_subscription" "nest_events_scrypted" {
  project                    = google_project.nest.project_id
  name                       = "nest-events-scrypted"
  topic                      = google_pubsub_topic.nest_events.id
  message_retention_duration = "3600s"

  push_config {
    push_endpoint = "https://nest-events.thurstons.house/${var.nest_events_token}"
  }

  expiration_policy {
    ttl = ""
  }
}

# Home Assistant's nest integration pulls with the linked user's OAuth token; select this
# subscription in its config flow instead of letting it create an expiring one.
resource "google_pubsub_subscription" "nest_events_home_assistant" {
  project                    = google_project.nest.project_id
  name                       = "nest-events-home-assistant"
  topic                      = google_pubsub_topic.nest_events.id
  message_retention_duration = "3600s"

  expiration_policy {
    ttl = ""
  }
}
