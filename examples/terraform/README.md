### Project Enabled Services (before running Terraform)
* serviceconsumermanagement.googleapis.com
* sqladmin.googleapis.com
* compute.googleapis.com

### Terraform Google Service Account (GSA) Required IAM Permissions

| Permission Name               | IAM Role                            | Description                                                                 |
| ----------------------------- | ----------------------------------- | --------------------------------------------------------------------------- |
| Artifact Registry Reader      | `roles/artifactregistry.reader`     | Allows read access to the repository containing the EPS Cloud Run image.    |
| Certificate Manager Owner     | `roles/certificatemanager.owner`    | Generates a Google-managed certificate for the load balancer.               |
| Cloud Build Connection Admin  | `roles/cloudbuild.connectionAdmin`  | Allows Cloud Build to connect to external source code repositories like GitHub. |
| Cloud Build Editor            | `roles/cloudbuild.builds.editor`    | Required to create and manage Cloud Build triggers.                         |
| Cloud Build WorkerPool Owner  | `roles/cloudbuild.workerPoolOwner`  | Creates private worker pools for Cloud Build for data loading.              |
| Cloud Run Admin               | `roles/run.admin`                   | Required for the EPS (Edge Parameter Store) application.                    |
| Cloud SQL Admin               | `roles/cloudsql.admin`              | EPS requires a database, and this setup presumes the use of Cloud SQL.      |
| Cloud Storage Admin           | `roles/storage.admin`               | Creates a Cloud Storage bucket to hold submitted jobs for Cloud Build.      |
| Compute Load Balancer Admin   | `roles/compute.loadBalancerAdmin`   | Manages the load balancer components associated with the application.       |
| Compute Network Admin         | `roles/compute.networkAdmin`        | Creates the necessary VPC, subnets, and other networking resources.         |
| DNS Admin                     | `roles/dns.admin`                   | Manages DNS zones in GCP.                                                   |
| IAP Policy Admin              | `roles/iap.admin`                   | Grants user access to the EPS application through Identity-Aware Proxy (IAP). |
| Project IAM Admin             | `roles/resourcemanager.projectIamAdmin` | Grants the Cloud Run GSA the necessary IAM access to Cloud SQL.             |
| Secret Manager Admin          | `roles/secretmanager.admin`         | Manages the application secrets related to EPS.                             |
| Serverless VPC Access Admin   | `roles/vpcaccess.admin`             | Creates a connector to allow serverless services to access resources in the VPC. |
| Service Account Admin         | `roles/iam.serviceAccountAdmin`     | Manages the Google Service Account (GSA) for Cloud Run.                     |
| Service Usage Admin           | `roles/serviceusage.serviceUsageAdmin` | Enables the services required by EPS.                                       |


### Cloud Build Data Loader

File: `terraform/opt-gcb-data-loader.tf` ([here](./opt-gcb-data-loader.tf))

This Cloud Build setup is used to run data loader scripts into the Cloud SQL database.  It used Cloud Build to provide
a preconfigured environment from which to load data through EPS into the Cloud SQL database.

The Google Cloud Build Service Account email (which looks like `gcb-eps-data-loader@my-project.iam.gserviceaccount.com`) requires
read access to the Artifact Registry location of the EPS image.  Consider using [Artifact Registry Reader](https://cloud.google.com/artifact-registry/docs/access-control#roles).
