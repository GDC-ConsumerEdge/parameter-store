# This file contains optional resources to enable running EPS data loader scripts through Cloud Build.
# This file is not necessary but helps.  See the repository README for more information.
resource "google_project_service" "build" {
  project            = var.eps_project_id
  service            = "cloudbuild.googleapis.com"
  disable_on_destroy = false
}

# GSA for Cloud Build
resource "google_service_account" "gcb" {
  account_id   = "gcb-${var.app_name_short}-data-loader"
  display_name = "gcb-${var.app_name_short}-data-loader"
  description  = "GCB Data Loader Service Account"
}

# GCB needs to be a Cloud SQL client
resource "google_project_iam_member" "gcb-sql" {
  project = var.eps_project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.gcb.email}"
}

# GCB needs to access the DB password in secret manager
data "google_iam_policy" "gcb-secret-access" {
  binding {
    role    = "roles/secretmanager.secretAccessor"
    members = ["serviceAccount:${google_service_account.gcb.email}"]
  }
}

# GCB needs to submit jobs and to write logs to cloud logging
resource "google_project_iam_member" "gcb-log-writer" {
  project = var.eps_project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.gcb.email}"
}

resource "google_storage_bucket" "gcb" {
  location                    = "us"
  name                        = "${data.google_project.eps.name}_cloudbuild"
  uniform_bucket_level_access = true
  force_destroy               = true
}

resource "google_storage_bucket_iam_member" "gcb" {
  bucket = google_storage_bucket.gcb.id
  role   = "roles/storage.admin"
  member = "serviceAccount:${google_service_account.gcb.email}"
}

output "gcb-data-loader-gsa" {
  value = google_service_account.gcb.id
}

resource "google_compute_global_address" "gcb" {
  name          = "build-worker-pool"
  purpose       = "VPC_PEERING"
  address_type  = "INTERNAL"
  prefix_length = 24
  network       = module.eps-network.network_id
  project       = var.eps_project_id
}

resource "google_cloudbuild_worker_pool" "pool" {
  name     = "eps-private-pool"
  location = var.region
  worker_config {
    disk_size_gb   = 100
    machine_type   = "e2-standard-4"
    no_external_ip = false
  }
  network_config {
    peered_network          = module.eps-network.network_id
    peered_network_ip_range = "/28"
  }
  depends_on = [google_service_networking_connection.sql, google_project_service.build]
}
