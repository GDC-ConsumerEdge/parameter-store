#!/bin/bash

set -e

SERVICE_ACCOUNT_NAME="parameter-store-tf"
PROJECT_ID=$(gcloud config get-value project)
SERVICE_ACCOUNT_EMAIL="${SERVICE_ACCOUNT_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

# IAM roles to be assigned to the service account
ROLES_TO_ADD=(
  "roles/artifactregistry.reader"
  "roles/certificatemanager.owner"
  "roles/cloudbuild.connectionAdmin"
  "roles/cloudbuild.workerPoolOwner"
  "roles/cloudsql.admin"
  "roles/compute.networkAdmin"
  "roles/dns.admin"
  "roles/iam.serviceAccountAdmin"
  "roles/iap.admin"
  "roles/resourcemanager.projectIamAdmin"
  "roles/run.admin"
  "roles/secretmanager.admin"
  "roles/serviceusage.serviceUsageAdmin"
  "roles/storage.admin"
  "roles/vpcaccess.admin"
)

echo -e "\nℹ️ Creating service account '${SERVICE_ACCOUNT_NAME}' in project '${PROJECT_ID}'..."

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

# Grant the current user account the Service Account Token Creator role on the Terraform service account
# This enables service account impersonation for the Terraform SA
echo -e "\nℹ️ Adding IAM Policy Binding for ${SERVICE_ACCOUNT_EMAIL}"

CURRENT_USER=$(gcloud config get-value account)
gcloud iam service-accounts add-iam-policy-binding "${SERVICE_ACCOUNT_EMAIL}" \
  --member="user:${CURRENT_USER}" \
  --role="roles/iam.serviceAccountTokenCreator"
