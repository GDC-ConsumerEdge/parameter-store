###############################################################################
# Copyright 2024 Google, LLC
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
# enable required APIs
resource "google_project_service" "default" {
  for_each           = toset(var.eps_project_services)
  project            = var.eps_project_id
  service            = each.value
  disable_on_destroy = false
}

resource "google_project_service" "secrets" {
  for_each           = toset(var.secrets_project_services)
  project            = local.secrets_project_id
  service            = each.value
  disable_on_destroy = false
}

# GSA for the app
resource "google_service_account" "eps" {
  account_id   = "${var.app_name_short}-app"
  display_name = "${var.app_name_short}-app"
  description  = "EPS app Cloud Run service"
}

# Terraform needs to act as the app GSA in order to deploy it
data "google_iam_policy" "terraform-access-to-run-gsa" {
  binding {
    role    = "roles/iam.serviceAccountUser"
    members = [var.terraform_principal]
  }
}

resource "google_service_account_iam_policy" "terraform" {
  service_account_id = google_service_account.eps.name
  policy_data        = data.google_iam_policy.terraform-access-to-run-gsa.policy_data
}

# EPS needs to be a Cloud SQL client
resource "google_project_iam_member" "eps-sql" {
  project = var.eps_project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.eps.email}"
}

# Grant IAP access to Cloud Run
resource "google_project_service_identity" "iap" {
  provider = google-beta

  project = var.eps_project_id
  service = "iap.googleapis.com"
}

resource "google_project_iam_member" "iap-run" {
  project = var.eps_project_id
  role    = "roles/run.invoker"
  member  = google_project_service_identity.iap.member
}

data "google_iam_policy" "admin" {
  binding {
    role    = "roles/iap.httpsResourceAccessor"
    members = var.eps_allowed_accessors
  }
}

resource "google_iap_web_iam_policy" "policy" {
  project     = var.eps_project_id
  policy_data = data.google_iam_policy.admin.policy_data
}
