data "google_project" "project" {
}

resource "google_project_iam_member" "cloudbuild_trigger_service_account_cloudbuild_invoker" {
  project = var.eps_project_id
  role    = "roles/cloudbuild.invoker"
  member  = "serviceAccount:${google_service_account.eps.email}"
}


resource "google_project_iam_member" "cloudbuild_secret_manager_admin" {
  project = var.eps_project_id
  role    = "roles/secretmanager.admin"
  member  = "serviceAccount:service-${google_service_account.eps.email}"
}



resource "google_cloudbuildv2_connection" "my-connection" {
  depends_on = [google_project_iam_member.cloudbuild_secret_manager_admin]
  location = "us-central1"
  name = "eps-connection"

  github_config {
    app_installation_id = var.github_app_installation_id
    authorizer_credential {
      oauth_token_secret_version = "projects/${data.google_project.project.number}/secrets/github-pat-secret/versions/1"
    }
  }
}

resource "google_cloudbuildv2_repository" "my-repository" {
  name = "parameter-store"
  parent_connection = google_cloudbuildv2_connection.my-connection.id
  remote_uri = "https://github.com/Cloudops-Google/parameter-store.git"
  location = "us-central1"
}

resource "google_cloudbuild_trigger" "cloudbuild_trigger_private_pool" {
  project = var.eps_project_id # Replace with your project ID
  name    = "eps-trigger" # Replace with your trigger name
  location = "us-central1" # Explicitly set the region

    repository_event_config {
    repository = google_cloudbuildv2_repository.my-repository.id
    push {
      branch = "main"
    }
    }
    filename = "cloudbuild.yaml"


    service_account = google_service_account.eps.email

}
