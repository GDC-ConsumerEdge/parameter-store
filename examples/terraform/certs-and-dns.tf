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

# This wires up a bunch of Google-managed certs in Certificate Manager, but it presumes that a zone is created
# specifically for ETS and that the zone is to be managed by this Terraform in Cloud DNS specifically for this app.
# This falls apart and is not usable if an adopting user cannot create and manage zones outside the management of
# centralized DNS.  In that case, certs will need to be provisioned using new resources.  Additionally,
# a record for the apps load balancer endpoint will need to be provisioned manually

resource "random_id" "dns" {
  byte_length = 2
}

resource "google_certificate_manager_dns_authorization" "default" {
  name        = "${var.app_name}-dnsauth-${random_id.dns.hex}"
  location    = var.region
  description = "The default DNS authorization; to be used by EPS; managed by Terraform"
  domain      = var.app_fqdn
  labels = {
    app = var.app_name_short
  }
}

resource "google_dns_managed_zone" "eps" {
  name        = replace(var.app_fqdn, ".", "-")
  dns_name    = "${var.app_fqdn}."
  description = "EPS managed DNS zone; managed by Terraform."
  labels = {
    app = var.app_name_short
  }
}

resource "google_dns_record_set" "cname" {
  name         = google_certificate_manager_dns_authorization.default.dns_resource_record[0].name
  managed_zone = google_dns_managed_zone.eps.name
  type         = google_certificate_manager_dns_authorization.default.dns_resource_record[0].type
  ttl          = 300
  rrdatas      = [google_certificate_manager_dns_authorization.default.dns_resource_record[0].data]
}

resource "google_certificate_manager_certificate" "eps" {
  name        = "${replace(var.app_fqdn, ".", "-")}-rootcert-${random_id.dns.hex}"
  location    = var.region
  description = "Google-managed cert"
  labels = {
    app = var.app_name_short
  }

  managed {
    domains            = [var.app_fqdn]
    dns_authorizations = [google_certificate_manager_dns_authorization.default.id]
  }
}

resource "google_dns_record_set" "a" {
  name         = "${var.app_fqdn}."
  managed_zone = google_dns_managed_zone.eps.name
  type         = "A"
  ttl          = 300
  rrdatas      = [google_compute_forwarding_rule.eps-fwd-rule.ip_address]
}