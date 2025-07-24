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


# For more detail on these variables please reference the Terraform Configuration Variables section of
# https://github.com/GDC-ConsumerEdge/parameter-store

environment_name = "dev"

# The GCP project id where the app (and nearly all) of its resources will be created
eps_project_id = "example-eps"

# The ID of a Google Cloud Project where app-related secrets are to be configured
# This may be the same as the eps_project_id
secrets_project_id = "example-eps"

# The GCP project id where Google Artifact Registry is configured
artifact_registry_project_id = "example-eps"

# The name of the repository within Artifact Registry where images will be stored and pulled
artifact_registry_repo = "parameter-store"

# The principal associated with the EPS Terraform deployment and is very likely a Google service account
terraform_principal = "serviceAccount:parameter-store-tf@example-eps.iam.gserviceaccount.com"

# The full name and tag of the image to be deployed by Terraform to Cloud Run
eps_image = "us-central-docker.pkg.dev/example-eps/parameter-store/parameter-store:latest"

# The name of the application image to be built or used
app_image_name = "parameter_store"

# The fully qualified domain name created for this project
app_fqdn = "example.eps.corp.net"

# A list of trusted origins for Cross-Site Request Forgery (CSRF) protection
csrf_trusted_origins = ["example.eps.corp.net", "dev.example.eps.corp.net"]

# iap_audience is the "audience" against which IAP JWT tokens are compared. This comes from the backend service
# associated with your load balancer stack. This value is not known until Terraform is run the first time, so on its
# first invocation, an empty string ("") is appropriate.
iap_audience = ""

# An array of users that will automatically receive EPS "superuser" permissions upon first login.
superusers = ["example"]

# An array of IAM principals that will be granted Cloud Run invoker and IAP accessor permissions
eps_allowed_accessors = ["group:eps@example.corp.net"]

# The name of the private worker pool that Cloud Build will use to execute the build
worker_pool_name = "eps-private-pool"

# The name or identifier of the secret in Google Secret Manager that stores the database password
db_password_key = "eps-db-pass"

# A connection name for the Cloud SQL instance
instance_connection_name = "example-eps:us-central1:eps-015b"

# The URL of the Git repository that Cloud Build will clone
git_repo_url = "https://github.com/example-eps/parameter-store.git"

# The email address to be configured for Git operations within the build environment
git_user_email = "example-eps@example.corp.net"

# The username to be configured for Git operations within the build environment
git_user_name = "example-eps-gituser"

# Cloud Build App id for your Github organization. This can be found within Github Organization settings or
# within your repository settings
github_app_id = "3325032727"

# A Github Personal Access Token used to integrate Github with Cloud Build
github_pat_token = ""
