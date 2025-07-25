data "google_project" "project" {
  depends_on = [
    google_project_service.default
  ]
}

resource "google_project_iam_member" "cloudbuild_secret_manager_admin" {
  project = var.eps_project_id
  role    = "roles/secretmanager.admin"
  member  = "serviceAccount:service-${data.google_project.project.number}@gcp-sa-cloudbuild.iam.gserviceaccount.com"
}


resource "google_secret_manager_secret" "github_pat_token" {
  secret_id = "github-pat-secret"
  replication {
    auto {}
  }
  deletion_protection = false
  depends_on = [
    google_project_service.default
  ]
}

resource "google_secret_manager_secret_version" "github_pat_token" {
  secret      = google_secret_manager_secret.github_pat_token.id
  secret_data = var.github_pat_token
}

resource "google_cloudbuildv2_connection" "my-connection" {
  depends_on = [google_project_iam_member.cloudbuild_secret_manager_admin]
  location   = var.region
  name       = "eps-connection"

  github_config {
    app_installation_id = var.github_app_id
    authorizer_credential {
      oauth_token_secret_version = google_secret_manager_secret_version.github_pat_token.id
    }
  }
}

resource "google_cloudbuildv2_repository" "my-repository" {
  name              = "parameter-store"
  parent_connection = google_cloudbuildv2_connection.my-connection.id
  remote_uri        = var.git_repo_url
  location          = var.region
}

resource "google_cloudbuild_trigger" "cloudbuild_trigger_private_pool" {
  depends_on = [time_sleep.wait_for_iam_propagation]
  project    = var.eps_project_id # Replace with your project ID
  name       = "eps-trigger"      # Replace with your trigger name
  location   = var.region

  # ... your other trigger configurations (repository, branch, etc.) ...

  repository_event_config {
    repository = google_cloudbuildv2_repository.my-repository.id
    push {
      branch = "main"
    }
  }
  substitutions = {
    # --- Database password secretmanager key ---
    _DATABASE_PASSWORD_KEY = var.db_password_key
    # --- Cloud SQL Proxy ---
    _PROXY_VERSION            = var.proxy_version
    _INSTANCE_CONNECTION_NAME = google_sql_database_instance.default.connection_name
    _PRIVATE_POOL             = "projects/${var.eps_project_id}/locations/${var.region}/workerPools/${var.worker_pool_name}" # Composed from vars
    # --- Artifact Registry / Image ---
    _ARTIFACT_REGISTRY_HOST       = var.artifact_registry_host
    _ARTIFACT_REGISTRY_PROJECT_ID = var.artifact_registry_project_id
    _ARTIFACT_REGISTRY_REPO       = var.artifact_registry_repo
    _APP_IMAGE_NAME               = var.app_image_name
    # --- Database (Using existing variables where possible) ---
    _DATABASE_USER = var.eps_db_user
    _DB_HOST       = var.db_host_template # Pass the template string from the variable
    _DATABASE_NAME = var.eps_db_name
    _DATABASE_PORT = var.database_port
    # --- Git Configuration ---
    _GIT_REPO_URL   = var.git_repo_url
    _GIT_USER_EMAIL = var.git_user_email
    _GIT_USER_NAME  = var.git_user_name
    _GIT_HOST       = var.git_host
  }
  filename = "cloudbuild.yaml"


  service_account = google_service_account.cloudbuild_gsa.id

}
