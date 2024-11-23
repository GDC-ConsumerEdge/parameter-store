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