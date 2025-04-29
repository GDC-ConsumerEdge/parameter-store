# GitHub Actions Workflows

This document describes the GitHub Actions workflows defined in the `examples/eps_to_csv/workflows/` directory for this repository.

## Repository Operating Modes (`MODE` Variable)

The behavior of several workflows depends on the value of the `MODE` repository variable. This variable dictates the primary source of truth for configuration:

*   **`GIT` Mode:** In this mode, the configuration source of truth is considered to be the files directly within the Git repository (e.g., the `cluster-intent-source-of-truth.csv` file). Changes are typically managed through standard Git pull requests, and hydration processes might be triggered directly based on file modifications within the repository. There will be no interaction with the EPS.
*   **`EPS` Mode:** In this mode, the primary source of truth is the external Edge Parameter Store (EPS). Workflows are designed to interact with EPS to:
    *   Check for configuration drift between the Git repository files and EPS.
    *   Fetch the latest configuration from EPS to update files in the Git repository (e.g., generating the SOT CSV).
    *   Reconcile differences found during drift checks.
    This mode is typically used when EPS manages the definitive state, and the Git repository needs to be kept in sync or validated against it.

The specific `MODE` set for the repository in the Github Actions variables determines which jobs within the workflows will execute.

## Workflows Overview

All the three workflows documented below call the resuable workflow [csv_updater_pipeline.yaml](./csv_updater_pipeline.yaml) with different parameters to invoke different jobs enabled by the resuable workflow. For more information on the configuration options of that workflow, please refer to [RESUABLE_WORKFLOW.md](./reusable_workflow.md)

*   **`manual_update_sot.yaml`**: A workflow dispatch that allows manual trigger of the Source of Truth (SOT) CSV generation process, typically used for cluster additions or updates. To hydrate new clusters that are added to EPS.
*   **`call_hydration_pipeline_full.yaml`**: Automatically checks for configuration drift against the Edge Parameter Store (EPS) when pull requests modify specific directories, and potentially triggers a hydration process if no drift is detected (when in EPS mode).
*   **`eps_commands_pipeline.yaml`**: Enables triggering EPS drift checks (`/fetch-eps`) or reconciliation (`/sync-eps`) via comments on open pull requests when the repository is in `EPS` mode.

---

### 1. `manual_update_sot.yaml` - Generate SOT CSV (Manual Trigger)

This workflow provides a way to manually generate or update a Source of Truth (SOT) CSV file based on data from the Edge Parameter Store (EPS). This is intended to be used for scenarios where clusters are added/modified in the EPS and need to be hydrated in the repositories.

**Trigger:**

*   Manually triggered via the GitHub Actions UI (`workflow_dispatch`).

**Usage:**

1.  Navigate to the "Actions" tab of the repository.
2.  Select the "Generate SOT CSV (Cluster Addition)" workflow from the list.
3.  Click the "Run workflow" button.
4.  Choose the appropriate `target_csv_file` from the dropdown. This should be the Source_of_truth file path in your repository that needs to be tracked & updated from EPS.
5.  Optionally, provide a `branch_suffix_override`.
6.  Click "Run workflow".

**Prerequisites/Repository Variables:**

This workflow relies on the following repository variables being correctly configured:

*   `MODE`: Must be set to `EPS` for the main job to run.
*   `SOURCE_OF_TRUTH_TYPE`: Defines the type of SOT being generated. ('intent' or 'template')
*   `GOOGLE_CLOUD_PROJECT`: GCP Project ID.
*   `WIF_PROVIDER`: Workload Identity Federation Provider URL.
*   `SERVICE_ACCOUNT`: GCP Service Account email with workload Identity Federation to Github Repo.
*   `EPS_HOST`: Hostname/URL of the Edge Parameter Store.
*   `EPS_CLIENT_ID`: Oauth IAP Client ID for authenticating with EPS.

---

### 2. `call_hydration_pipeline_full.yaml` - Check and Run Hydration

This workflow automatically runs on pull requests that modify files within the `hydrated/` or `templates/` directories. 

In `EPS` mode : 
* It checks for configuration drift against the Edge Parameter Store (EPS). 
* If no drift is detected, it proceeds ** trigger the actual hydration process. 

If `GIT` mode : 
*  Upon trigger, directly runs hydration bypassing the step for checking drift from EPS.

**Trigger:**

*   Pull requests (`pull_request`) targeting the main branch with types: `opened`, `synchronize`, `reopened`.
*   Runs only if changes occur in paths: `hydrated/**` or `templates/**`.

**Usage:**

*   This workflow runs automatically when pull requests meeting the trigger criteria are opened or updated. 
*   It is intended for when template file changes are made in the cluster manifest repositories like `edge-workloads`, `edge-platform`.
*   When pull requests are created to the main branch, this workflow orchestrates the process of validation of SourceOfTruth and hydration.

**Prerequisites/Repository Variables:**

This workflow relies on the following repository variables being correctly configured:

*   `MODE`: Determines the execution path (`GIT` or `EPS`).
*   `SOURCE_OF_TRUTH_TYPE`: Used to determine the correct CSV file path when in `EPS` mode.
*   `GOOGLE_CLOUD_PROJECT`: GCP Project ID (for `EPS` mode).
*   `WIF_PROVIDER`: Workload Identity Federation Provider URL (for `EPS` mode).
*   `SERVICE_ACCOUNT`: GCP Service Account email (for `EPS` mode).
*   `EPS_HOST`: Hostname/URL of the Edge Parameter Store (for `EPS` mode).
*   `EPS_CLIENT_ID`: Oauth IAPClient ID for authenticating with EPS (for `EPS` mode).

---

### 3. `eps_commands_pipeline.yaml` - EPS Commands via PR Comments

This workflow allows triggering actions related to the Edge Parameter Store (EPS) by posting specific commands as comments on open pull requests. It only runs when the repository variable `MODE` is set to `EPS`. The commands are disabled in `GIT` mode.

**Trigger:**

*   Issue comments (`issue_comment`) of type `created`.

**Usage:**

1.  Ensure the repository variable `MODE` is set to `EPS`.
2.  On an open Pull Request, add a comment containing *exactly* `/fetch-eps` or `/sync-eps`.
3.  Run `/fetch-eps` to verify if the repository source_of_truth is up-to-date with the EPS data.
4.  If any drift is detected, Run `\sync-eps` command to generate the latest source_of_truth from EPS and commit to your source branch on the Pull Request.
5.  Because the pull_request is now synchronized, the [call_hydration_pipeline_full](./call_hydration_pipeline_full.yaml) workflow gets triggered and runs hydration.
6.  Based on the command run, the workflow will trigger, add an initial "eyes" reaction as acknowledgement. 
7.  It then run the reusable workflow with the required parameters, and update the comment reaction based on the outcome.
8.  Results/reports from the reusable workflow are posted as separate comments on the PR.

**Prerequisites/Repository Variables:**

This workflow relies on the following repository variables being correctly configured:

*   `MODE`: Must be set to `EPS` for the main jobs to run.
*   `SOURCE_OF_TRUTH_TYPE`: Used to determine the correct CSV file path to be tracked and updated.
*   `GOOGLE_CLOUD_PROJECT`: GCP Project ID.
*   `WIF_PROVIDER`: Workload Identity Federation Provider URL.
*   `SERVICE_ACCOUNT`: GCP Service Account email.
*   `EPS_HOST`: Hostname/URL of the Edge Parameter Store.
*   `EPS_CLIENT_ID`: Oauth IAP Client ID for authenticating with EPS.

---


## Installation
please refer to [RESUABLE_WORKFLOW.md](./reusable_workflow.md) for setting up the Centralized reusable workflow. Once that is completed, simply place the [config](../config/) directory and [workflows](../workflows/) directory with the required caller workflows in your caller repository. Set the required environment variables and update the `uses:` and `used_workflow_ref` fields in the jobs in your caller workflows to point to the resuable workflow file. That's it!