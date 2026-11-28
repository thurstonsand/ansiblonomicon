resource "google_project" "colab" {
  name            = "Colab"
  project_id      = "ansiblonomicon-colab"
  billing_account = local.billing_account
}

resource "google_project_service" "colab" {
  project = google_project.colab.project_id
  service = "colaboratory.googleapis.com"
}
