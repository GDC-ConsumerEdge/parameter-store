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

data "google_iam_policy" "eps-secret-access" {
  binding {
    role = "roles/secretmanager.secretAccessor"
    members = [
      "serviceAccount:${google_service_account.eps.email}",
      "serviceAccount:${google_service_account.gcb.email}" # TODO: remove if not using Cloud Build
    ]
  }
}

#
#  Cloud SQL Database Password
#
resource "random_password" "database" {
  length           = 30
  override_special = "!@#$^&-=_"
}

resource "google_secret_manager_secret" "eps-db-pass" {
  secret_id = "${var.app_name_short}-db-pass"
  project   = var.secrets_project_id

  labels = {
    app  = var.app_name_short
    tier = "db"
  }

  replication {
    auto {}
  }

  depends_on = [google_project_service.secrets]
}

resource "google_secret_manager_secret_version" "eps-db-pass" {
  secret      = google_secret_manager_secret.eps-db-pass.id
  secret_data = random_password.database.result
}


resource "google_secret_manager_secret_iam_policy" "eps-db-pass" {
  project     = google_secret_manager_secret.eps-db-pass.project
  secret_id   = google_secret_manager_secret.eps-db-pass.id
  policy_data = data.google_iam_policy.eps-secret-access.policy_data
}

#
# Django Secret Key
#
resource "random_password" "eps-secret" {
  length = 50
}

resource "google_secret_manager_secret" "eps-secret" {
  secret_id = "${var.app_name_short}-app-secret"
  project   = var.secrets_project_id

  labels = {
    app  = var.app_name_short
    tier = "app"
  }

  replication {
    auto {}
  }

  depends_on = [google_project_service.secrets]
}

resource "google_secret_manager_secret_version" "eps-secret" {
  secret      = google_secret_manager_secret.eps-secret.id
  secret_data = random_password.eps-secret.result
}

resource "google_secret_manager_secret_iam_policy" "eps-secret" {
  project     = google_secret_manager_secret.eps-secret.project
  secret_id   = google_secret_manager_secret.eps-secret.id
  policy_data = data.google_iam_policy.eps-secret-access.policy_data
}
