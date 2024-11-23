# Copyright 2024 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

variable "project_id" {
  description = "The Google Cloud Platform (GCP) project id in which the solution resources will be provisioned"
  type        = string
}

variable "project_id_fleet" {
  description = "Optional id of GCP project hosting the Google Kubernetes Engine (GKE) fleet or Google Distributed Compute Engine (GDCE) machines. Defaults to the value of 'project_id'."
  default     = null
  type        = string
}

variable "project_id_secrets" {
  description = "Optional id of GCP project containing the Secret Manager entry storing Git repository credentials. Defaults to the value of 'project_id'."
  default     = null
  type        = string
}

variable "region" {
  description = "GCP region to deploy resources"
  type        = string
}

variable "store_id" {
  description = "store id of McD"
  type = string
}

variable "project_services" {
  type        = list(string)
  description = "GCP Service APIs (<api>.googleapis.com) to enable for this project"
  default = [
#     "cloudbuild.googleapis.com",
#     "cloudfunctions.googleapis.com",
#     "cloudscheduler.googleapis.com",
#     "run.googleapis.com",
#     "storage.googleapis.com",
  ]
}

# prune list of required services later
variable "project_services_fleet" {
  type        = list(string)
  description = "GCP Service APIs (<api>.googleapis.com) to enable for this project"
  default = [
#     "anthos.googleapis.com",
#     "anthosaudit.googleapis.com",
#     "anthosconfigmanagement.googleapis.com",
#     "anthosgke.googleapis.com",
    "artifactregistry.googleapis.com",
#     "cloudbuild.googleapis.com",
#     "cloudfunctions.googleapis.com",
#     "cloudresourcemanager.googleapis.com",
#     "cloudscheduler.googleapis.com",
    "connectgateway.googleapis.com",
#     "container.googleapis.com",
#     "edgecontainer.googleapis.com",
#     "gkeconnect.googleapis.com",
#     "gkehub.googleapis.com",
#     "gkeonprem.googleapis.com",
    "iam.googleapis.com",
    "iamcredentials.googleapis.com",
    "iap.googleapis.com",
    "identitytoolkit.googleapis.com",
    "logging.googleapis.com",
    "monitoring.googleapis.com",
    "opsconfigmonitoring.googleapis.com",
    "run.googleapis.com",
    "secretmanager.googleapis.com",
    "serviceusage.googleapis.com",
    "sql-component.googleapis.com",
    "sqladmin.googleapis.com",
    "stackdriver.googleapis.com",
#     "storage.googleapis.com",
    "sts.googleapis.com",
    "vpcaccess.googleapis.com",
  ]
}

variable "project_services_secrets" {
  type        = list(string)
  description = "GCP Service APIs (<api>.googleapis.com) to enable for this project"
  default = [
    "secretmanager.googleapis.com",
  ]
}

variable "environment" {
  description = "Deployment environment"
  type        = string
}

variable "skip_identity_service" {
  description = "Skip the configuring Anthos identity service during cluster provisioning. This is used for group based RBAC in the cluster."
  type        = bool
  default     = false
}

variable "source_of_truth_repo" {
  description = "Source of truth repository"
  default     = "gitlab.com/gcp-solutions-public/retail-edge/gdce-shyguy-internal/cluster-intent-registry"
}

variable "source_of_truth_branch" {
  description = "Source of truth branch"
  default     = "main"
}

variable "source_of_truth_path" {
  description = "Path to cluster intent registry file"
  default     = "source_of_truth.csv"
}

variable "git_secret_id" {
  description = "Secrets manager secret holding git token to pull source of truth"
  default     = "shyguy-internal-pat"
}

variable "deploy-zone-active-monitor" {
  type        = bool
  description = "Whether to deploy Zone Active Monitor cloud function"
  default     = false
}

variable "edge_container_api_endpoint_override" {
  description = "Google Distributed Cloud Edge API. Leave empty to use default api endpoint."
  default     = ""
}

variable "edge_network_api_endpoint_override" {
  description = "Google Distributed Cloud Edge Network API. Leave empty to use default api endpoint."
  default     = ""
}

variable "gke_hub_api_endpoint_override" {
  description = "Google Distributed Cloud Edge API. Leave empty to use default api endpoint."
  default     = ""
}

variable "hardware_management_api_endpoint_override" {
  description = "Google Distributed Hardware Management API. Leave empty to use default api endpoint."
  default     = ""
}

variable "cluster-creation-timeout" {
  description = "Cloud Build timeout in seconds for cluster creation. This should account for time to create the cluster, configure core services (ConfigSync, Robin, VMRuntime, etc..), and time for any workload configuration needed before the healthchecks pass."
  default     = "28800"
  type        = number
}

variable "django_port" {
  description = "TCP port where django admin site runs"
  default = 8080
  type = number
}

variable "eps_vpc_access_cidr" {
  description = "The CIDR range for Private VPC Access between EPS Cloud RUN instance and Cloud SQL DB"
  type = string
  default = "10.8.0.0/28"
  validation {
    condition     = can(cidrsubnet(var.eps_vpc_access_cidr, 0, 0))
    error_message = "Invalid EPS VPC ACCESS CIDR block format."
  }
}

variable "eps_vpc_access_min_throughput" {
  description = "The Min Throughput of EPS Private VPC Access (Mbps)"
  type = number
  default = 200
}

variable "eps_vpc_access_max_throughput" {
  description = "The Max Throughput of EPS Private VPC Access (Mbps)"
  type = number
  default = 1000
}

variable "eps_db_instance" {
  description = "The name of the Cloud SQL Postgres Instance"
  type = string
}

variable "eps_db_name" {
  description = "The name of the Cloud SQL Postgres DB"
  type = string
}

variable "eps_db_user" {
  description = "The username of the Cloud SQL Postgres DB"
  type = string
}

variable "eps_db_password" {
  description = "The user password of the Cloud SQL Postgres DB"
  type = string
}

variable "vpc_name" {
  description = "The name of the VPC where the all the resources located"
  type = string
  default = "default"
}

variable "subnet_name" {
  description = "The name of the subnet in VPC where the all the resources located"
  type = string
  default = "default"
}

variable "eps_cert_name" {
  description = "The name of the region self signed cert for eps"
  type = string
  default = "eps-cert"
}

variable "iap_enabled" {
  description = "Whether use with IAP. true: validate JWT with IAP public key. false: validate JWT with Google public key"
  type = bool
  default = true
}

variable "csrf_trusted_origins"{
  description = "The trusted CSRF origins. Put the DNS domain name of the app to here."
  type = list(string)
  default = ["*.internal", "*.localhost"]
}
