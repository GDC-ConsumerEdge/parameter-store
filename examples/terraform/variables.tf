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
variable "eps_image" {
  description = "EPS container image; this is the full path to be pulled"
  type        = string
}

variable "eps_project_id" {
  description = "The Google Cloud Platform (GCP) project id in which the solution resources will be provisioned"
  type        = string
}

variable "secrets_project_id" {
  description = "Optional ID of GCP project for Secret Manager secrets. If left empty, it defaults to the value of 'eps_project_id'."
  type        = string
  default     = ""
}

variable "region" {
  description = "GCP region to deploy resources"
  type        = string
  default     = "us-central1"
}

variable "replication_region" {
  description = "Secondary GCP region for replication where applicable"
  type        = string
  default     = "us-east4"
}

variable "eps_project_services" {
  type        = list(string)
  description = "GCP Service APIs (<api>.googleapis.com) to enable for this project"
  default = [
    "artifactregistry.googleapis.com",
    "certificatemanager.googleapis.com",
    "cloudresourcemanager.googleapis.com",
    "dns.googleapis.com",
    "iam.googleapis.com",
    "iap.googleapis.com",
    "logging.googleapis.com",
    "monitoring.googleapis.com",
    "run.googleapis.com",
    "secretmanager.googleapis.com",
    "servicenetworking.googleapis.com",
    "sqladmin.googleapis.com",
    "vpcaccess.googleapis.com",
  ]
}

variable "secrets_project_services" {
  type        = list(string)
  description = "GCP Service APIs (<api>.googleapis.com) to enable for this project"
  default = [
    "secretmanager.googleapis.com",
  ]
}

variable "environment_name" {
  description = "Deployment environment"
  type        = string
}

variable "app_name" {
  description = "Name of the app; default is good; this is available as an override"
  default     = "edge-parameter-store"
  type        = string
}

variable "app_name_short" {
  description = "Short name of the app where space must be preserved; default is good; this is available as an override"
  default     = "eps"
  type        = string
}

variable "app_fqdn" {
  description = "Fully qualified domain name for the EPS frontend"
  type        = string
}

variable "django_port" {
  description = "TCP port where Django listens"
  default     = 8080
  type        = number
}

variable "eps_vpc_access_cidr" {
  description = "The CIDR range for Private VPC Access between EPS Cloud RUN instance and Cloud SQL DB"
  type        = string
  default     = "10.8.0.0/28"
  validation {
    condition     = can(cidrsubnet(var.eps_vpc_access_cidr, 0, 0))
    error_message = "Invalid EPS VPC ACCESS CIDR block format."
  }
}

variable "eps_vpc_access_min_throughput" {
  description = "The Min Throughput of EPS Private VPC Access (Mbps)"
  type        = number
  default     = 200
}

variable "eps_vpc_access_max_throughput" {
  description = "The Max Throughput of EPS Private VPC Access (Mbps)"
  type        = number
  default     = 1000
}

variable "eps_db_instance" {
  description = "The name of the Cloud SQL Postgres Instance"
  type        = string
  default     = "eps"
}

variable "eps_db_name" {
  description = "The name of the Cloud SQL Postgres DB name; this is not the instance name, it is the database within the instance"
  type        = string
  default     = "eps"
}

variable "eps_db_user" {
  description = "The username of the Cloud SQL Postgres DB"
  type        = string
  default     = "eps"
}


variable "subnet_name" {
  description = "The name of the subnet in VPC where the all the resources located"
  type        = string
  default     = "eps"
}

variable "iap_enabled" {
  description = "Whether use with IAP; recommended to use as best practice"
  type        = bool
  default     = true
}

variable "iap_audience" {
  description = "Audience to scope to JWT token. Isn't known until after the first run.  Recommended as best practice."
  type        = string
}

variable "csrf_trusted_origins" {
  description = "The trusted CSRF origins. Put the DNS domain name of the app to here."
  type        = list(string)
  default     = []
}

variable "terraform_principal" {
  description = "The principal used by Terraform at deployment time in the form of memberType:email; ex: serviceAccount:terraform@myproject.iam.gserviceaccount.com"
  type        = string
}

variable "eps_allowed_accessors" {
  description = "Principals to grant IAP accessor IAM access to the EPS endpoint as IAM principals, ex: group:group@example.com; user:user@example.com; serviceAccount:some-gsa@myproject.iam.gserviceaccount.com"
  type        = list(string)
  default     = []
}

variable "superusers" {
  description = "Comma separated list of users who, upon first login, become app superusers; usernames only, which is everything before the @ in the email"
  type        = list(string)
  default     = []
}

variable "worker_pool_name" {
  description = "Name of the private worker pool."
  type        = string
  default     = "eps-private-pool" # Or make it required by removing default
}

variable "db_password_key" {
  description = "Secret Manager key name for the database password."
  type        = string
  # No default, should be provided per environment
}

variable "proxy_version" {
  description = "Version of the Cloud SQL Proxy to use."
  type        = string
  default     = "v2.15.1"
}

variable "instance_connection_name" {
  description = "Cloud SQL instance connection name (project:region:instance)."
  type        = string
  # No default, should be provided per environment
}

variable "artifact_registry_host" {
  description = "Hostname for the Artifact Registry (e.g., us-docker.pkg.dev)."
  type        = string
  default     = "us-docker.pkg.dev"
}

variable "artifact_registry_project_id" {
  description = "Project ID where the Artifact Registry resides."
  type        = string
  # No default, often same as eps_project_id but could differ
}

variable "artifact_registry_repo" {
  description = "Artifact Registry repository name."
  type        = string
}

variable "app_image_name" {
  description = "Base name for the container image."
  type        = string
}


# Note: _DB_HOST uses another substitution, so we pass the template string
# It could be made more dynamic if needed, but this keeps the Cloud Build logic
variable "db_host_template" {
  description = "Template for DB host using Cloud Build substitution for instance connection name."
  type        = string
  default     = "/cloudsql/$${_INSTANCE_CONNECTION_NAME}" # Note the $$ to escape Terraform interpolation
}


variable "database_port" {
  description = "Database port."
  type        = string # Keep as string as substitutions expect strings
  default     = "5432"
}

variable "git_repo_url" {
  description = "Full URL to the Git repository."
  type        = string
}

variable "git_user_email" {
  description = "Email for Git commits within the build."
  type        = string
}

variable "git_user_name" {
  description = "Username for Git commits within the build."
  type        = string
}

variable "git_host" {
  description = "Hostname of the Git provider (e.g., github.com)."
  type        = string
  default     = "github.com"
}


variable "source_branch_name" {
  description = "The branch to trigger the build on."
  type        = string
  default     = "main"
}

variable "trigger_service_account_email" {
  description = "Email of the service account for the trigger."
  type        = string
}

variable "github_app_id" {
  description = "Cloud Build app id for your Github organisation. This is the numeric ID of the GitHub App installation."
  type        = number
}
