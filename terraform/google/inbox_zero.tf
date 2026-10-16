# Inbox Zero on pod042 signs in with this project's OAuth client and receives Gmail push
# notifications through inbox-zero-emails. Google Auth Platform (branding, audience, OAuth
# clients) has no API, so the client is recorded here after being created by hand. The
# app is published to production so Gmail refresh tokens outlive Testing's seven days;
# its privacy and terms links point at upstream because the self-hosted app serves neither.
locals {
  inbox_zero_oauth_client_id = "477070056163-vg0linamgdkf8c2m9s7187uhtptbddid.apps.googleusercontent.com"
}

output "inbox_zero_oauth_client_id" {
  value = local.inbox_zero_oauth_client_id
}

resource "google_project" "inbox_zero" {
  name            = "Inbox Zero"
  project_id      = "inbox-zero-248085"
  billing_account = local.billing_account
}

resource "google_project_service" "inbox_zero" {
  for_each = toset([
    "calendar-json.googleapis.com",
    "drive.googleapis.com",
    "gmail.googleapis.com",
    "people.googleapis.com",
    "pubsub.googleapis.com",
  ])

  project = google_project.inbox_zero.project_id
  service = each.value
}

resource "google_pubsub_topic" "inbox_zero_emails" {
  project = google_project.inbox_zero.project_id
  name    = "inbox-zero-emails"

  depends_on = [google_project_service.inbox_zero]
}

# Gmail's users.watch publishes mailbox changes as this Google-owned service account.
resource "google_pubsub_topic_iam_member" "inbox_zero_emails_gmail_publisher" {
  project = google_project.inbox_zero.project_id
  topic   = google_pubsub_topic.inbox_zero_emails.name
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:gmail-api-push@system.gserviceaccount.com"
}

# Inbox Zero rejects pushes whose token query parameter differs from GOOGLE_PUBSUB_VERIFICATION_TOKEN.
variable "inbox_zero_pubsub_verification_token" {
  type      = string
  sensitive = true
}

resource "google_pubsub_subscription" "inbox_zero_emails_webhook" {
  project = google_project.inbox_zero.project_id
  name    = "inbox-zero-emails-webhook"
  topic   = google_pubsub_topic.inbox_zero_emails.id

  push_config {
    push_endpoint = "https://inbox.thurstons.house/api/google/webhook?token=${var.inbox_zero_pubsub_verification_token}"
  }

  expiration_policy {
    ttl = ""
  }
}

output "inbox_zero_pubsub_topic" {
  value = google_pubsub_topic.inbox_zero_emails.id
}
