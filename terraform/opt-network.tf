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

# This sets up a basic network which is referenced throughout this example module. It's reasonable to expect that this
# module and network setup will never be use because enterprise users will likely have prescriptive network
# configuration and, as such, this should go away. Once removed, search for use of this module and wire up the existing
# network data as needed.  Consider using network data sources in Terraform.

module "eps-network" {
  source       = "terraform-google-modules/network/google"
  version      = "~> 10.0"
  project_id   = var.eps_project_id
  network_name = var.app_name_short
  mtu          = 1460

  subnets = [
    {
      subnet_name   = "${var.app_name_short}-${var.region}"
      subnet_ip     = "10.100.128.0/24"
      subnet_region = var.region
    },
    {
      subnet_name   = "${var.app_name_short}-proxy-${var.region}"
      subnet_ip     = "10.100.129.0/26"
      subnet_region = var.region
      role          = "ACTIVE"
      purpose       = "REGIONAL_MANAGED_PROXY"
    }
  ]

  depends_on = [google_project_service.default]
}
