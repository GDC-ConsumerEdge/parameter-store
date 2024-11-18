locals {
  project_id_fleet   = coalesce(var.project_id_fleet, var.project_id)
  project_id_secrets = coalesce(var.project_id_secrets, var.project_id)
}

data "google_compute_network" "main" {
  name    = var.vpc_name
  project = local.project_id_fleet
}

data "google_compute_subnetwork" "main" {
  name    = var.subnet_name
  region  = var.region
  project = local.project_id_fleet
}

data "google_sql_database_instance" "eps_db" {
  name    = var.eps_db_name
  project = local.project_id_fleet
}

# # Seems region is not supported with ssl certifcates
# data "google_compute_ssl_certificate" "eps_cert" {
#   name    = var.eps_cert_name
#   project = local.project_id_fleet
# }

# # certificate manager certificate not supported yet
# data "google_certificate_manager_certificate" "eps_cert" {
#   name      = var.eps_cert_name
#   project   = local.project_id_fleet
#   location  = var.region
# }

resource "google_vpc_access_connector" "eps_vpc_access" {
  name          = "eps-vpc-access"
  region        = var.region # Replace with your region
  ip_cidr_range = var.eps_vpc_access_cidr # Specify a custom IP range
  network       = data.google_compute_network.main.name # Replace with your VPC network name
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
      env {
        name = "GOOGLE_CLOUD_PROJECT"
        value = local.project_id_fleet
      }
      env {
        name = "REGION"
        value = var.region
      }
      env {
        name = "PROJECT_ID_SECRETS"
        value = local.project_id_secrets
      }
      env {
        name = "GIT_SECRET_ID"
        value = ""
      }
      env {
        name = "SOURCE_OF_TRUTH_REPO"
        value = ""
      }
      env {
        name = "SOURCE_OF_TRUTH_BRANCH"
        value = ""
      }
      env {
        name = "SOURCE_OF_TRUTH_PATH"
        value = ""
      }
    }
  }
}

resource "google_compute_region_network_endpoint_group" "eps_neg" {
  name                  = "eps-neg"
  region                = var.region
  network_endpoint_type = "SERVERLESS"
  cloud_run {
    service = google_cloud_run_v2_service.eps_web.name
  }
}

resource "google_compute_region_backend_service" "eps_lb_backend_svc" {
  name                  = "eps-lb-backend-service"
  region                = var.region
  protocol              = "HTTPS"
  load_balancing_scheme = "INTERNAL_MANAGED"
  iap {
    enabled             = true
  }
  backend {
    group               = google_compute_region_network_endpoint_group.eps_neg.id
  }
}

resource "google_compute_region_url_map" "eps_url_map" {
  name            = "eps-url-map"
  region          = var.region
  default_service = google_compute_region_backend_service.eps_lb_backend_svc.id
}

resource "google_compute_region_target_https_proxy" "eps_https_proxy" {
  name             = "eps-https-proxy"
  region           = var.region
  url_map          = google_compute_region_url_map.eps_url_map.id
#   ssl_certificates = [data.google_compute_ssl_certificate.eps_cert.id]
#   ssl_certificates = ["https://certificatemanager.googleapis.com/v1/projects/${local.project_id_fleet}/locations/${var.region}/certificates/${var.eps_cert_name}"]
  ssl_certificates = ["//www.googleapis.com/compute/beta/projects/${local.project_id_fleet}/regions/${var.region}/sslCertificates/${var.eps_cert_name}"]
}

resource "google_compute_forwarding_rule" "eps_fwd_rule" {
  name                  = "eps-lb-forwarding-rule"
  region                = var.region
  ip_protocol           = "TCP"
  load_balancing_scheme = "INTERNAL_MANAGED"
  port_range            = 443
  allow_global_access   = true
  target                = google_compute_region_target_https_proxy.eps_https_proxy.id
  network               = data.google_compute_network.main.id
  subnetwork            = data.google_compute_subnetwork.main.id
}