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
# environment         = "staging"
# store_id            = "dryrun2-cam-8cc"
# project_id          = "daniel-test-proj-411311"
# region              = "us-central1"
# eps_db_name         = "cloud-sql--daniel-2"
# project_id_secrets  = "cloud-alchemists-sandbox"

environment         = "testing"
store_id            = "dryrun2-cam-8cc"
project_id          = "danielxia-sandbox"
region              = "us-central1"

eps_db_instance     = "test-db"
eps_db_name         = "eps"
eps_db_user         = "eps"
eps_db_password     = "123456"

project_id_secrets      = "danielxia-sandbox"
source_of_truth_repo    = "gitlab.com/daniell76/test_2"
source_of_truth_branch  = "main"
source_of_truth_path    = "test_sot_iap.csv"
git_secret_id           = "daniel-gl-pat"

csrf_trusted_origins    = ["*.internal", "*.localhost"]