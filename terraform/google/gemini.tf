resource "google_project" "gemini" {
  name            = "Gemini API"
  project_id      = "gen-lang-client-0166268742"
  billing_account = local.billing_account
  labels = {
    generative-language = "enabled"
  }
}

resource "google_project_service" "gemini_generative_language" {
  project = google_project.gemini.project_id
  service = "generativelanguage.googleapis.com"
}

# Gemini CLI sign-in through cli-proxy-api.
resource "google_project_service" "gemini_code_assist" {
  project = google_project.gemini.project_id
  service = "cloudaicompanion.googleapis.com"
}

resource "google_service_account" "gemini_api_key" {
  project      = google_project.gemini.project_id
  account_id   = "gemini-api-key"
  display_name = "Gemini API key"
}

# Binding a service account makes this an auth key, the only kind the Gemini API accepts.
resource "google_apikeys_key" "gemini" {
  project               = google_project.gemini.project_id
  name                  = "gemini"
  display_name          = "Gemini"
  service_account_email = google_service_account.gemini_api_key.email

  restrictions {
    api_targets {
      service = google_project_service.gemini_generative_language.service
    }
  }
}

output "gemini_api_key" {
  value     = google_apikeys_key.gemini.key_string
  sensitive = true
}
