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


# The GCP Project ID where the EPS bootstrap configs will be applied. This will be the same GCP project that will run EPS.
gcp_project_id = "example-eps"

# The GCP user account which will run the bootstrap process. This user requires the following GCP IAM Roles:
# Project IAM Admin
# Service Account Admin
terraform_user_principal = "user:user@corp.net"

# The name of the service account to be created for Terraform.
# This should match the 'terraform_sa_name' used in the main configuration.
terraform_sa_name = "parameter-store-tf"
