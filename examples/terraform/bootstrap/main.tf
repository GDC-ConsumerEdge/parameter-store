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
###

# For more detail on these variables please reference the Terraform Configuration Variables section of
# https://github.com/GDC-ConsumerEdge/parameter-store

# This configuration is used to bootstrap the necessary IAM resources for the main
# Terraform project. It should be run once by a user with sufficient permissions
# to create service accounts and assign IAM roles.

variable "gcp_project_id" {
  description = "The GCP project ID where the resources will be created."
  type        = string
}

variable "terraform_user_principal" {
  description = "The principal of the user who will be running the main Terraform apply, in the format 'user:{email}' (e.g., 'user:jane@example.com')."
  type        = string
}

variable "terraform_sa_name" {
  description = "The name of the service account to be created for Terraform."
  type        = string
  default     = "parameter-store-tf"
}

resource "google_service_account" "terraform_sa" {
  project      = var.gcp_project_id
  account_id   = var.terraform_sa_name
  display_name = "Parameter Store Terraform GSA"
}

variable "roles_to_add" {
  description = "The list of IAM roles to be assigned to the Terraform service account."
  type        = list(string)
  default = [
    "roles/artifactregistry.reader",
    "roles/certificatemanager.owner",
    "roles/cloudbuild.connectionAdmin",
    "roles/cloudbuild.builds.editor",
    "roles/cloudbuild.workerPoolOwner",
    "roles/cloudsql.admin",
    "roles/compute.loadBalancerAdmin",
    "roles/compute.networkAdmin",
    "roles/dns.admin",
    "roles/iam.serviceAccountAdmin",
    "roles/iap.admin",
    "roles/resourcemanager.projectIamAdmin",
    "roles/run.admin",
    "roles/secretmanager.admin",
    "roles/serviceusage.serviceUsageAdmin",
    "roles/storage.admin",
    "roles/vpcaccess.admin"
  ]
}

resource "google_project_iam_member" "terraform_sa_roles" {
  for_each = toset(var.roles_to_add)
  project  = var.gcp_project_id
  role     = each.key
  member   = "serviceAccount:${google_service_account.terraform_sa.email}"
}


resource "google_service_account_iam_member" "user_can_impersonate" {
  service_account_id = google_service_account.terraform_sa.name
  role               = "roles/iam.serviceAccountTokenCreator"
  member             = var.terraform_user_principal
}

output "terraform_service_account_email" {
  description = "The email address of the created Terraform service account."
  value       = google_service_account.terraform_sa.email
}
