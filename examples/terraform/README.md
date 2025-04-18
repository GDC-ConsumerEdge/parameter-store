### Project Enabled Services (before running Terraform)
* serviceconsumermanagement.googleapis.com
* sqladmin.googleapis.com 
* compute.googleapis.com

### Terraform GSA IAM Perms
* Cloud Run Admin
  * EPS app
* Cloud SQL Admin
  * EPS requires a DB and presumes Cloud SQL
* Compute Load Balancer Admin
  * App related load balancer components
* Compute Network Admin
  * Create VPC, subnets, 
* Secret Manager Admin
  * To create EPS-related app secrets  
* Serverless VPC Access Admin
  * To create serverless VPC connector
* Service Usage Admin
  * Enable EPS-required services
* Service Account Admin 
  * for Cloud Run GSA
* Project IAM Admin
  * to grant Cloud Run GSA IAM access to Cloud SQL 
* Artifact Registry Reader (
  * on repo for EPS Cloud Run image
* Certificate Manager Owner 
  * Generates a Google-managed cert for LB that fronts the EPS app
* DNS Admin 
  * Managing zones in GCP to be used by Cert Manager and as app FQDN
* IAP Policy Admin
  * Grant user access to EPS app through IAP
* Cloud Storage Admin
  * To create Cloud Build storage bucket to hold submitted jobs
  * Optional if using Cloud Build data loader features
* Cloud Build WorkerPool Owner
  * To create Cloud Build private worker pools for data loading
  * Optional if using Cloud build data loader features

### Cloud Build Data Loader

File: `terraform/opt-gcb-data-loader.tf` ([here](./opt-gcb-data-loader.tf))

This Cloud Build setup is used to run data loader scripts into the Cloud SQL database.  It used Cloud Build to provide 
a preconfigured environment from which to load data through EPS into the Cloud SQL database.  

The Google Cloud Build Service Account email (which looks like `gcb-eps-data-loader@my-project.iam.gserviceaccount.com`) requires
read access to the Artifact Registry location of the EPS image.  Consider using [Artifact Registry Reader](https://cloud.google.com/artifact-registry/docs/access-control#roles).