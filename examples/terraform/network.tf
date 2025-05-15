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

#
# Private services access
#
resource "google_compute_global_address" "sql" {
  name          = "sql"
  purpose       = "VPC_PEERING"
  address_type  = "INTERNAL"
  prefix_length = 24
  network       = module.eps-network.network_id
  project       = var.eps_project_id
}

resource "google_service_networking_connection" "sql" {
  network = module.eps-network.network_id

  service = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [
    google_compute_global_address.sql.name,
    google_compute_global_address.gcb.name # TODO: remove if not using GCB data loader
  ]
  deletion_policy         = "ABANDON" # Read docs on this, it has consequences
  update_on_creation_fail = true
}


#
# EPS app on Cloud Run load balancer
#
resource "google_compute_region_network_endpoint_group" "eps-neg" {
  name                  = "${var.app_name_short}-neg"
  region                = var.region
  network_endpoint_type = "SERVERLESS"

  cloud_run {
    service = google_cloud_run_v2_service.eps.name
  }
}

resource "google_compute_region_backend_service" "eps-lb-backend-service" {
  name                  = "${var.app_name_short}-lb-backend-service"
  region                = var.region
  protocol              = "HTTPS"
  load_balancing_scheme = "EXTERNAL_MANAGED"

  iap {
    enabled = true
  }

  backend {
    group           = google_compute_region_network_endpoint_group.eps-neg.id
    capacity_scaler = 1.0
  }

  lifecycle {
    ignore_changes = [iap]
  }

  # the service identity needs to be created and IAM granted to the IAP service agent before we create this
  depends_on = [google_project_iam_member.iap-run]
}

resource "google_compute_region_url_map" "eps_url_map" {
  name            = "${var.app_name_short}-url-map"
  region          = var.region
  default_service = google_compute_region_backend_service.eps-lb-backend-service.id
}

resource "google_compute_region_target_https_proxy" "eps-https-proxy" {
  name                             = "${var.app_name_short}-https-proxy"
  region                           = var.region
  url_map                          = google_compute_region_url_map.eps_url_map.id
  certificate_manager_certificates = [google_certificate_manager_certificate.eps.id]

  depends_on = [module.eps-network]
}

resource "google_compute_forwarding_rule" "eps-fwd-rule" {
  name                  = "${var.app_name_short}-lb-forwarding-rule"
  region                = var.region
  network               = module.eps-network.network_name
  port_range            = 443
  ip_protocol           = "TCP"
  load_balancing_scheme = "EXTERNAL_MANAGED"
  target                = google_compute_region_target_https_proxy.eps-https-proxy.id
  # allow_global_access   = true # only for 'INTERNAL_MANAGED'
  # ip_address            = data.google_compute_address.eps_lb_ip.address
  # subnetwork            = data.google_compute_subnetwork.main.id
}
