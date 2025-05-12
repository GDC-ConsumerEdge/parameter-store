# CSV Merger Script (`csv_merger.py`)

This script is intended to be used for updating the template source_of_truth.csv file containing the platform and workload revision versions in the cluster-registry repositories when RollOut Manager is being used.

This Python script updates a target CSV file with new rows from a source CSV file, using the `cluster_name` column as the unique key. It's designed to maintain a consistent structure in the target CSV.

## Purpose

The primary goal of this script is to:
1.  **Preserve Existing Data**: If a `cluster_name` from the source CSV (generated from EPS) already exists in the target CSV, the entire row for that cluster in the target CSV is kept as is.
2.  **Add New Data**: If a `cluster_name` from the source CSV does not exist in the target CSV, a new row is added.
    *   Data for `cluster_name`, `cluster_group`, and `cluster_tags` is taken from the source CSV for these new entries.
    *   `platform_repository_revision` and `workload_repository_revision` for these new rows can be set to user-provided default values or left blank.
3.  **Maintain Strict Output Structure**: The target CSV will always be structured with the following five columns, in this specific order:
    *   `cluster_name`
    *   `cluster_group`
    *   `cluster_tags`
    *   `platform_repository_revision`
    *   `workload_repository_revision`
    Any other columns present in the source CSV will be ignored for new rows, and any pre-existing extra columns in the target CSV will be removed.

## Usage

The script is run from the command line or any Github Action pipelines.

```bash
python csv_merger.py <source_csv_path> <target_csv_path> [options]
```

### Arguments:

*   `source_csv`: Path to the source CSV file (e.g., newly generated data from EPS). This file must contain at least a `cluster_name` column.
*   `target_csv`: Path to the target CSV file to be updated (e.g., a source-of-truth file in a Git repository). If this file doesn't exist, it will be created.

### Options:

*   `--default-platform-revision <value>`: Optional. Default value for the `platform_repository_revision` column for new cluster entries. If not provided, this field will be blank for new rows.
*   `--default-workload-revision <value>`: Optional. Default value for the `workload_repository_revision` column for new cluster entries. If not provided, this field will be blank for new rows.