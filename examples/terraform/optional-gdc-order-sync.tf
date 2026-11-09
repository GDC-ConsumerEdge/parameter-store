###############################################################################
# Copyright 2026 Google, LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
###############################################################################
# Optional resources for syncing GDC hardware orders into EPS via Cloud Run Jobs.
# Disabled by default (var.enable_gdc_order_sync = false) so UI-only deployments
# do not provision extra service accounts or cross-project IAM bindings.

locals {
  gdc_sync_account_id = "${var.app_name_short}-gdc-sync"

  gdc_sync_services = var.enable_gdc_order_sync ? toset([
    "cloudscheduler.googleapis.com",
    "iamcredentials.googleapis.com",
  ]) : toset([])

  gdc_sync_projects = var.enable_gdc_order_sync ? toset(var.gdc_order_project_ids) : toset([])
}

resource "google_project_service" "gdc_sync" {
  for_each           = local.gdc_sync_services
  project            = var.eps_project_id
  service            = each.value
  disable_on_destroy = false
}

resource "google_service_account" "gdc_sync" {
  count        = var.enable_gdc_order_sync ? 1 : 0
  project      = var.eps_project_id
  account_id   = local.gdc_sync_account_id
  display_name = local.gdc_sync_account_id
  description  = "Service Account for syncing GDC orders into EPS"
  depends_on = [
    google_project_service.default,
    google_project_service.gdc_sync,
  ]
}

# Wait briefly for GSA global IAM propagation before authoritative IAP policy binding
resource "time_sleep" "wait_for_gdc_sync_gsa" {
  count           = var.enable_gdc_order_sync ? 1 : 0
  depends_on      = [google_service_account.gdc_sync]
  create_duration = "15s"
}

# Allow the sync SA to mint short-lived IAP signed JWTs for itself via IAM Credentials API
resource "google_service_account_iam_member" "gdc_sync_token_creator" {
  count              = var.enable_gdc_order_sync ? 1 : 0
  service_account_id = google_service_account.gdc_sync[0].name
  role               = "roles/iam.serviceAccountTokenCreator"
  member             = "serviceAccount:${google_service_account.gdc_sync[0].email}"
}

# Allow Cloud Scheduler (using this SA) to trigger the Cloud Run Job (:run endpoint)
resource "google_project_iam_member" "gdc_sync_run_developer" {
  count   = var.enable_gdc_order_sync ? 1 : 0
  project = var.eps_project_id
  role    = "roles/run.developer"
  member  = "serviceAccount:${google_service_account.gdc_sync[0].email}"
}

# Allow the sync SA to invoke Cloud Run services in the EPS host project
resource "google_project_iam_member" "gdc_sync_run_invoker" {
  count   = var.enable_gdc_order_sync ? 1 : 0
  project = var.eps_project_id
  role    = "roles/run.invoker"
  member  = "serviceAccount:${google_service_account.gdc_sync[0].email}"
}

# Optional: Grant read-only GDC Hardware Management access on target GDC project(s)
resource "google_project_iam_member" "gdc_sync_hardware_reader" {
  for_each = local.gdc_sync_projects
  project  = each.value
  role     = "roles/gdchardwaremanagement.reader"
  member   = "serviceAccount:${google_service_account.gdc_sync[0].email}"
}

output "gdc_sync_service_account_email" {
  description = "Email of the optional GDC Order Sync Service Account (null when disabled)"
  value       = var.enable_gdc_order_sync ? google_service_account.gdc_sync[0].email : null
}
