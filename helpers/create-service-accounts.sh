#!/bin/bash

set -e

SERVICE_ACCOUNT_NAME="parameter-store-tf"
PROJECT_ID=$(gcloud config get-value project)
SERVICE_ACCOUNT_EMAIL="${SERVICE_ACCOUNT_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

# IAM roles to be assigned to the service account
ROLES_TO_ADD=(
  "roles/run.admin"
  "roles/cloudsql.admin"
  "roles/compute.networkAdmin"
  "roles/secretmanager.admin"
  "roles/vpcaccess.admin"
  "roles/serviceusage.serviceUsageAdmin"
  "roles/iam.serviceAccountAdmin"
  "roles/resourcemanager.projectIamAdmin"
  "roles/artifactregistry.reader"
  "roles/certificatemanager.owner"
  "roles/dns.admin"
  "roles/iap.admin"
  "roles/storage.admin"
  "roles/cloudbuild.workerPoolOwner"
)

echo "Creating service account '${SERVICE_ACCOUNT_NAME}' in project '${PROJECT_ID}'..."

gcloud iam service-accounts create "${SERVICE_ACCOUNT_NAME}" \
  --display-name="Parameter Store Terraform GSA" \
  --project="${PROJECT_ID}"

# Loop through the roles and add them to the service account
for role in "${ROLES_TO_ADD[@]}"; do
  echo -e "\nAdding role ${role} to ${SERVICE_ACCOUNT_NAME}..."

  gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
    --member="serviceAccount:${SERVICE_ACCOUNT_EMAIL}" \
    --role="${role}" \
    --condition=None > /dev/null
done

echo -e "\n✅ Successfully created the "${SERVICE_ACCOUNT_NAME}" service account and assigned all roles."
