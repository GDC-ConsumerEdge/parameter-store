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
  # collapse secrets into the EPS (primary) project if not set
  secrets_project_id = coalesce(var.secrets_project_id, var.eps_project_id)
}

data "google_project" "eps" {
  project_id = var.eps_project_id
  depends_on = [
    google_project_service.default
  ]
}
