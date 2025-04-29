# Reusable Workflow: CSV Updater Pipeline (`csv_updater_resuable_pipeline.yaml`)

## Overview

This reusable workflow provides a standardized process for updating a Source of Truth (SOT) CSV file within the repository. Its behavior adapts based on the `source_of_truth_type` and `chatops_mode` inputs.

* **`intent` SOURCE_OF_TRUTH_TYPE:** Generates the `cluster intent` source of truth. This is intended for repositories like `edge-cluster-registry` that store intent data tracked by solutions like Automated Cluster Provisioner

* **`template` SOURCE_OF_TRUTH_TYPE:** Generates the `cluster template` (also referred to as `cluster data`) source of truth. This source-of-truth file is used to hydrate the cluster platform and workload manifests in repositories such as `edge-platform` and `edge-workloads`.

* **`check` chatops_mode:** This value runs the workflow to check for changes/drift in the data from EPS against `target_csv_file` input file path present in the caller repository. It prints a command whether drift is detected or not with the diff if applicable. It also generates an output `drift_detected` with boolean values to be used as conditional to enable dynamic workflows.

* **`reconcile` chatops_mode:** This value runs the workflow to update/sync the `target_csv_file` input file in the repository with the latest data fetched from EPS. It commits the file to the source branch of the PR and prints a PR comment. It also generates an output `sync_performed` with boolean values to be used as conditional to enable dynamic workflows.

* **`empty` chatops_mode:** If no value is set, then the workflow runs in the "default mode".


## Usage

To utilize this reusable workflow (`csv_updater_resuable_pipeline.yaml`), you need to call it from another GitHub Actions workflow file. The `uses:` keyword specifies the path to the reusable workflow in your caller workflows. You will need to provide specific `inputs` to control its behavior (like `source_of_truth_type` and `chatops_mode` as discussed above) and pass the necessary `secrets` and `inputs` for authentication and access (especially when interacting with EPS).

Please refer to [call_hydration_pipeline_full](./call_hydration_pipeline_full.yaml), [eps_commands_pipeline](./eps_commands_pipeline.yaml), and [manual_update_sot](./manual_update_sot.yaml) and their [README](./README.md) for reference examples on how this can be utilized for different usecases.


## Prerequisites

For this reusable workflow to function correctly, the following components and configurations are expected:

1.  **Python Script and Dependencies file:**
    *   The Python script responsible for fetching data from EPS and generating the target CSV file
    *   It is recommended to have it in a separate [resources](../resources/) folder in the resuable workflow repository under `./github` directory along with its `requirements.txt` file.
    *   However, The path to this script can be provided via the `python_script_path` input (you can also set the defaults within the inputs section of the workflow if not provided).
    *   Please check the [Python Script README](../resources/README.md) file and make sure the required dependencies are met.

4.  **Caller Workflow with Configuration (secrets and variables):**
    *   A correctly configured calling workflow that specifies the `uses:` path, provides the required `inputs`, and passes the necessary `secrets`.
    *   Necessary GitHub secrets (like `EPS_HOST`, `EPS_CLIENT_ID`, GCP WIF credentials) must be configured in the repository or organization settings and passed to the workflow.




