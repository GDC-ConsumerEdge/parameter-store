locals {
  project_id_fleet   = coalesce(var.project_id_fleet, var.project_id)
}

data "google_sql_database_instance" "eps_db" {
  name    = "cloud-sql--daniel-2"
  project = local.project_id_fleet
}

resource "google_vpc_access_connector" "eps_vpc_access" {
  name          = "eps-vpc-access"
  region        = var.region # Replace with your region
  ip_cidr_range = var.eps_vpc_access_cidr # Specify a custom IP range
  network       = var.eps_vpc_access_vpc # Replace with your VPC network name
#   max_instances = 10
#   min_instances = 2
  min_throughput  = var.eps_vpc_access_min_throughput
  max_throughput  = var.eps_vpc_access_max_throughput
}

resource "google_cloud_run_v2_service" "eps_web" {
  name     = "edge-parameter-store"
  location = var.region
  deletion_protection = false
  depends_on = [google_vpc_access_connector.eps_vpc_access]
  template {
    vpc_access {
      connector = google_vpc_access_connector.eps_vpc_access.id
      egress    = "ALL_TRAFFIC" # Route all traffic through the connector
    }
    containers {
      image = "gcr.io/daniel-test-proj-411311/parameter-store/parameter-store:latest"
      ports {
        name           = "http1" # Must be empty, "http1", or "h2c"
        container_port = var.django_port
      }
#       liveness_probe {
#         initial_delay_seconds = 5 # Initial delay before the first probe (seconds)
#         timeout_seconds       = 5  # How long to wait for each probe (seconds)
#         period_seconds        = 10 # Interval between probes (seconds)
#         failure_threshold     = 3  # Number of consecutive failures before restarting
#         http_get {
#           path = "/params"
#         }
#       }
      env {
        name = "DB_HOST"
        value = data.google_sql_database_instance.eps_db.private_ip_address
      }
      env {
        name = "DB_USER"
        value = "eps"
      }
      env {
        name = "DB_PASSWORD"
        value = "123456"
      }
      env {
        name = "DB_NAME"
        value = "eps"
      }
      env {
        name = "DJANGO_PORT"
        value = var.django_port
      }
    }
  }
}
