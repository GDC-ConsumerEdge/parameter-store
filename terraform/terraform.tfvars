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

# these environment variables are examples
# TODO: before release, fix these up as dummy examples without leaking googler info
environment_name      = "dev"
eps_project_id        = "durivage-eps"
secrets_project_id    = "durivage-eps"
eps_image             = "us-docker.pkg.dev/durivage-eps/hsp/parameter_store:v11"
terraform_principal   = "serviceAccount:terraform@durivage-eps.iam.gserviceaccount.com"
app_fqdn              = "durivage.eps.joonix.net"
csrf_trusted_origins  = ["localhost"]
iap_audience          = "/projects/22368248810/us-central1/backendServices/6252277272778218001"
superusers            = ["durivage", "bfogel", "anmolsachdeva", "psabhishek", "jpandurangan", "kodrama"]
eps_allowed_accessors = ["group:eps@durivage.joonix.net"]