# **Edge Parameter Store \- Infrastructure Overview**

This document outlines the GCP architecture for the Edge Parameter Store (EPS) application. The design is implemented in
Terraform and assumes a target audience familiar with GCP resources and Terraform syntax.

The core of the application is a Django project deployed as a `google_cloud_run_v2_service`. Traffic is routed through
a Global External HTTPS Load Balancer, which handles SSL termination using a Google-managed certificate and maps to the
user-provided domain. Access to the application is secured by Identity-Aware Proxy (IAP), which restricts access to the
principals defined in the `var.iap_users` input variable. This creates a zero-trust overlay without requiring a VPN or
modifications to the application code for user authentication at the perimeter.

The application's state is maintained in a `google_sql_database_instance` running Postgres. The Cloud Run service does
not connect to the database over its public IP. Instead, it communicates over the internal network via a
`google_vpc_access_connector`, ensuring traffic between the application and the database does not traverse the public
internet. Database credentials and other sensitive configurations are supplied to the Cloud Run service via environment
variables. The values for these variables are stored securely in Secret Manager; the Cloud Run service's identity is
granted IAM permissions to access these secrets at runtime.

Continuous integration is handled by Cloud Build. A `google_cloudbuild_trigger` monitors the source code repository. On
a push to the specified branch, it executes the steps defined in `cloudbuild.yaml`, which include building the service's
Docker container, pushing it to the Artifact Registry, and subsequently running Django database migrations. An optional,
separate Cloud Build process using a private worker pool (`google_cloudbuild_worker_pool`) is available for initial
data seeding, as detailed in [examples/data_loader/](../examples/data_loader).

Deployment involves a necessary two-step process due to a circular dependency inherent in the IAP configuration.

1. Run `terraform apply` for the initial resource creation. This will fail during the Cloud Run service configuration
   because the IAP audience, which is required by Django, has not been generated yet.
2. The initial apply will, however, successfully create the `google_iap_brand` and `google_iap_client`. The `client_id`
   and client_secret from the output of this partial apply must then be used to update the `IAP_CLIENT_ID` and
   `IAP_CLIENT_SECRET` secrets in Secret Manager.
3. Run `terraform apply` a second time. With the correct IAP audience values now present in Secret Manager, the Cloud Run
   service will deploy successfully.

This two-step bring-up is a critical operational note for the initial deployment or if the IAP configuration is ever
destroyed and recreated.
