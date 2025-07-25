terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = ">=6.45.0"
    }
  }
}

provider "google" {
  project = var.gcp_project_id
}
