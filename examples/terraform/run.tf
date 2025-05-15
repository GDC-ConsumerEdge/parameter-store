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
locals {
  csrf_trusted_origins = distinct(compact([
    var.app_fqdn,
    join(",", var.csrf_trusted_origins)
  ]))
}

resource "random_bytes" "eps-run" {
  length = 2
}

resource "google_cloud_run_v2_service" "eps" {
  name                = "${var.app_name}-${random_bytes.eps-run.hex}"
  location            = var.region
  deletion_protection = false
  ingress             = "INGRESS_TRAFFIC_INTERNAL_LOAD_BALANCER"
  labels = {
    app  = var.app_name_short
    tier = "app"
  }

  scaling {
    min_instance_count = 1
  }

  template {
    service_account = google_service_account.eps.account_id

    vpc_access {
      network_interfaces {
        network    = module.eps-network.network_id
        subnetwork = module.eps-network.subnets["${var.region}/${var.app_name_short}-${var.region}"].id
      }
      egress = "PRIVATE_RANGES_ONLY" # Route only internal traffic through the connector
    }

    containers {
      image = var.eps_image

      ports {
        name           = "http1" # Must be empty, "http1", or "h2c"
        container_port = var.django_port
      }

      resources {
        limits = {
          "cpu"  = "1000m"
          memory = "2Gi"
        }
        startup_cpu_boost = true
      }

      liveness_probe {
        initial_delay_seconds = 15 # Initial delay before the first probe (seconds)
        timeout_seconds       = 10 # Number of seconds after which the probe times out (seconds)
        period_seconds        = 15 # Interval between probes (seconds)
        failure_threshold     = 3  # Number of consecutive failures before restarting

        http_get {
          path = "/api/v1/status"
        }
      }

      startup_probe {
        initial_delay_seconds = 5 # Initial delay before the first probe (seconds)
        timeout_seconds       = 5 # Number of seconds after which the probe times out (seconds)
        failure_threshold     = 3 # Number of consecutive failures before restarting

        http_get {
          path = "/api/v1/ping"
        }
      }


      volume_mounts {
        mount_path = "/cloudsql"
        name       = "cloudsql"
      }

      env {
        name  = "DJANGO_PORT"
        value = var.django_port
      }

      env {
        name = "DJANGO_SECRET_KEY"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.eps-secret.id
            version = "latest"
          }
        }
      }

      env {
        name  = "DB_HOST"
        value = "/cloudsql/${google_sql_database_instance.default.connection_name}"
      }

      env {
        name  = "DB_NAME"
        value = var.eps_db_name
      }

      env {
        name  = "DB_USER"
        value = var.eps_db_user
      }

      env {
        name = "DB_PASSWORD"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.eps-db-pass.id
            version = "latest"
          }
        }
      }

      env {
        name  = "PARAM_STORE_IAP_ENABLED"
        value = var.iap_enabled
      }

      env {
        name  = "PARAM_STORE_IAP_AUDIENCE"
        value = var.iap_audience
      }

      dynamic "env" {
        for_each = length(var.superusers) > 0 ? [true] : []
        content {
          name  = "PARAM_STORE_SUPERUSERS"
          value = join(",", var.superusers)
        }
      }

      dynamic "env" {
        for_each = length(local.csrf_trusted_origins) > 0 ? [true] : []
        content {
          name  = "CSRF_TRUSTED_ORIGINS"
          value = join(",", local.csrf_trusted_origins)
        }
      }

    }

    volumes {
      name = "cloudsql"
      cloud_sql_instance {
        instances = [google_sql_database_instance.default.connection_name]
      }
    }
  }

  depends_on = [
    google_service_account_iam_policy.terraform,
    google_secret_manager_secret_iam_policy.eps-db-pass
  ]
}
