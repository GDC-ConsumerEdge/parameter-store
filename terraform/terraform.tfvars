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
eps_project_id        = "example-eps"
secrets_project_id    = "example-eps"
eps_image             = "us-docker.pkg.dev/example-eps/hsp/parameter_store:v15"
terraform_principal   = "serviceAccount:terraform@example-eps.iam.gserviceaccount.com"
app_fqdn              = "example.eps.corp.net"
csrf_trusted_origins  = ["localhost"]
iap_audience          = "/projects/22368248810/us-central1/backendServices/506473743633145264"
superusers            = ["example"]
eps_allowed_accessors = ["group:eps@example.corp.net"]
worker_pool_name                = "eps-private-pool"
db_password_key                 = "eps-db-pass" # Or fetch from a secure source if needed at plan time
instance_connection_name        = "eps-cicd:us-central1:eps-015b"
artifact_registry_project_id    = "eps-cicd"
artifact_registry_repo          = "eps"
app_image_name                  = "parameter_store"
git_repo_url                    = "https://github.com/Cloudops-Google/parameter-store.git"
git_user_email                  = "psabhishek@google.com"
git_user_name                   = "psabhishekgoogle"
# source_repo_id is likely derived from another resource, not set here directly
# source_branch_name uses default "main"
trigger_service_account_email   = "terraform@eps-cicd.iam.gserviceaccount.com"
