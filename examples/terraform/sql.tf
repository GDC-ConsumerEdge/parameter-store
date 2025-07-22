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
resource "random_id" "db_name_suffix" {
  byte_length = 2
}

resource "google_sql_database_instance" "default" {
  name                = "${var.eps_db_instance}-${random_id.db_name_suffix.hex}"
  project             = var.eps_project_id
  region              = var.region
  database_version    = "POSTGRES_17"
  instance_type       = "CLOUD_SQL_INSTANCE"
  deletion_protection = false

  settings {
    activation_policy           = "ALWAYS"
    availability_type           = "REGIONAL"
    connector_enforcement       = "REQUIRED"
    deletion_protection_enabled = false
    disk_autoresize             = true
    disk_autoresize_limit       = 0
    disk_size                   = 10
    disk_type                   = "PD_SSD"
    edition                     = "ENTERPRISE"
    pricing_plan                = "PER_USE"
    tier                        = "db-custom-2-4096" # decent start for prod
    # tier                        = "f1-micro"  # for dev
    user_labels = {
      app  = var.app_name_short
      tier = "db"
    }

    backup_configuration {
      backup_retention_settings {
        retained_backups = 14
        retention_unit   = "COUNT"
      }
      enabled                        = true
      location                       = "us"
      point_in_time_recovery_enabled = true
      start_time                     = "06:00"
      transaction_log_retention_days = 7
    }

    insights_config {
      query_insights_enabled = true
    }

    ip_configuration {
      ipv4_enabled    = false
      private_network = module.eps-network.network_self_link
      psc_config {
        psc_enabled               = true
        allowed_consumer_projects = [var.eps_project_id]
        # consumer_network          = [module.eps-network.network_id]
      }
    }

    maintenance_window {
      day  = 6
      hour = 6
    }
  }

  depends_on = [
    google_project_service.default,
    google_service_networking_connection.sql,
  ]
}


resource "google_sql_user" "users" {
  name            = var.eps_db_user
  instance        = google_sql_database_instance.default.name
  password        = random_password.database.result
  type            = "BUILT_IN"
  deletion_policy = "ABANDON"
}

resource "google_sql_database" "database" {
  name     = var.eps_db_name
  instance = google_sql_database_instance.default.name
}
