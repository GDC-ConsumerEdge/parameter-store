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