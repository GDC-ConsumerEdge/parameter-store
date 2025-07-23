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

terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = ">=6.45.0"
    }
    google-beta = {
      source  = "hashicorp/google-beta"
      version = ">=6.45.0"
    }
  }

  # Configure backend when using in prod
  # backend "gcs" {}
}
locals {
  terraform_service_account_email = length(split(":", var.terraform_principal)) > 1 ? split(":", var.terraform_principal)[1] : var.terraform_principal
}

provider "google" {
  project                     = var.eps_project_id
  impersonate_service_account = local.terraform_service_account_email
}

provider "google-beta" {
  project                     = var.eps_project_id
  impersonate_service_account = local.terraform_service_account_email
}
