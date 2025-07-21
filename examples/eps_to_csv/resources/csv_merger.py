import argparse
import logging
import os
import sys
from pathlib import Path
import pandas as pd

# --- Setup Logging ---
logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

# Define the default columns for the target CSV, used if the target is new or its structure is invalid.
DEFAULT_EXPECTED_TARGET_COLUMNS = [
    "cluster_name",
    "cluster_group",
    "cluster_tags",
    "platform_repository_revision",
    "workload_repository_revision",
]


def update_csv_with_new_rows(
    source_csv_path_str: str,
    target_csv_path_str: str,
    default_platform_rev: str | None = None,
    default_workload_rev: str | None = None,
):
    """
    Updates the target CSV file with new rows from the source CSV file,
    keyed by 'cluster_name'.

    - If a 'cluster_name' from source exists in target, the target row is kept as is.
    - If a 'cluster_name' from source does not exist in target, a new row is added.
        - For new rows, 'cluster_name', 'cluster_group', 'cluster_tags' are taken from the source.
        - 'platform_repository_revision' and 'workload_repository_revision' are set to provided defaults or left blank.
        - Other columns (if the target structure has more than the defaults) will be populated from the source if available, otherwise left blank.
    - The target CSV will conform to the column structure of the existing target file, provided it's valid (contains 'cluster_name').
      If the target file is new, empty, or has an invalid structure, DEFAULT_EXPECTED_TARGET_COLUMNS will be used.
      No other columns from the source will be added. Existing extra columns in target will be removed.

    Args:
        source_csv_path_str: Path to the source CSV file (e.g., newly generated).
        target_csv_path_str: Path to the target CSV file to be updated (e.g., in Git).
        default_platform_rev: Optional default value for 'platform_repository_revision' for new rows.
        default_workload_rev: Optional default value for 'workload_repository_revision' for new rows.
    """
    source_csv_path = Path(source_csv_path_str)
    target_csv_path = Path(target_csv_path_str)
    current_expected_columns = DEFAULT_EXPECTED_TARGET_COLUMNS[:]

    if not source_csv_path.is_file():
        logger.error(f"Source CSV file not found: {source_csv_path}")
        raise FileNotFoundError(f"Source CSV file not found: {source_csv_path}")

    try:
        source_df = pd.read_csv(source_csv_path)
    except pd.errors.EmptyDataError:
        logger.info(f"Source CSV '{source_csv_path}' is empty. No new rows to add.")
        if not target_csv_path.exists():
            logger.info(
                f"Target CSV '{target_csv_path}' does not exist. Creating an empty one with expected columns (as source was empty)."
            )
            pd.DataFrame(columns=current_expected_columns).to_csv(target_csv_path, index=False, encoding="utf-8")
        return
    except Exception as e:
        logger.error(f"Error reading source CSV '{source_csv_path}': {e}", exc_info=True)
        raise

    if "cluster_name" not in source_df.columns:
        logger.error(f"'cluster_name' column not found in source CSV: {source_csv_path}. Cannot proceed.")
        raise ValueError(f"'cluster_name' column missing in source CSV {source_csv_path}")

    original_target_df_existed = target_csv_path.is_file() and target_csv_path.stat().st_size > 0
    num_rows_in_original_target = 0

    if original_target_df_existed:
        try:
            target_df = pd.read_csv(target_csv_path)
            logger.info(f"Read {len(target_df)} row(s) from existing target CSV: {target_csv_path}")
            num_rows_in_original_target = len(target_df)
            if not target_df.empty and target_df.columns.any():
                derived_columns = target_df.columns.tolist()
                if "cluster_name" not in derived_columns:
                    logger.warning(
                        f"Existing target CSV '{target_csv_path}' does not contain the required 'cluster_name' column. "
                        f"Falling back to default column structure: {current_expected_columns}"
                    )
                else:
                    current_expected_columns = derived_columns
                    logger.info(f"Using column structure from existing target: {current_expected_columns}")
            else:  # Target existed but was empty or had no columns
                logger.info(
                    f"Target CSV '{target_csv_path}' is empty or has no columns. Using default column structure: {current_expected_columns}"
                )
        except pd.errors.EmptyDataError:
            logger.info(f"Target CSV '{target_csv_path}' exists but is empty. Will treat as new.")
            target_df = pd.DataFrame()  # Start with empty DataFrame
            original_target_df_existed = False
            logger.info(f"Using default column structure for empty target: {current_expected_columns}")
        except Exception as e:
            logger.error(f"Error reading target CSV '{target_csv_path}': {e}", exc_info=True)
            raise
    else:
        logger.info(
            f"Target CSV '{target_csv_path}' not found. Using default column structure for new file: {current_expected_columns}"
        )
        target_df = pd.DataFrame()  # Start with empty DataFrame

    # Identify new cluster_names from source_df
    source_cluster_names = set(source_df["cluster_name"].dropna().unique())

    if not target_df.empty and "cluster_name" in target_df.columns:
        target_cluster_names = set(target_df["cluster_name"].dropna().unique())
    else:
        target_cluster_names = set()
        if not target_df.empty and "cluster_name" not in target_df.columns:
            logger.warning(
                f"Target CSV '{target_csv_path}' exists but lacks 'cluster_name' column. All source entries will be treated as new if they have 'cluster_name'."
            )

    new_cluster_names_to_add = source_cluster_names - target_cluster_names

    new_rows_list = []
    if new_cluster_names_to_add:
        logger.info(f"Identified {len(new_cluster_names_to_add)} new cluster name(s) to add from source.")
        for cluster_name_to_add in new_cluster_names_to_add:
            # Get the first row matching the cluster_name (in case of duplicates in source)
            source_row_series = source_df[source_df["cluster_name"] == cluster_name_to_add]
            if source_row_series.empty:
                # Should not happen if new_cluster_names_to_add was derived correctly
                logger.warning(
                    f"Cluster name '{cluster_name_to_add}' was in new_cluster_names_to_add but not found in source_df during iteration. Skipping."
                )
                continue
            source_row = source_row_series.iloc[0]

            new_row_data = {}
            # Populate based on current_expected_columns
            for col_name in current_expected_columns:
                if col_name == "cluster_name":
                    # cluster_name must exist in source_row if this logic is reached. though these conditions for cluster_name, cluster_group and cluster_tags..
                    # are not neccessary, keeping them explicitly for better readability and future changes on these important fields.
                    new_row_data[col_name] = source_row.get("cluster_name", pd.NA)
                elif col_name == "cluster_group":
                    new_row_data[col_name] = source_row.get("cluster_group", pd.NA)
                elif col_name == "cluster_tags":
                    new_row_data[col_name] = source_row.get("cluster_tags", pd.NA)
                elif col_name == "platform_repository_revision":
                    new_row_data[col_name] = default_platform_rev if default_platform_rev is not None else pd.NA
                elif col_name == "workload_repository_revision":
                    new_row_data[col_name] = default_workload_rev if default_workload_rev is not None else pd.NA
                else:
                    # For any other columns expected in the target, try to get them from source,
                    # otherwise they will be NA (blank in CSV).
                    new_row_data[col_name] = source_row.get(col_name, pd.NA)
            new_rows_list.append(new_row_data)
    else:
        logger.info("No new cluster_names found in source to add to target.")

    if new_rows_list:
        new_rows_df = pd.DataFrame(new_rows_list)
        # Ensure new_rows_df has exactly the EXPECTED_TARGET_COLUMNS in the correct order
        new_rows_df = new_rows_df.reindex(columns=current_expected_columns)
    else:
        new_rows_df = pd.DataFrame(columns=current_expected_columns)  # Empty DF with correct columns

    # Combine original target_df with the processed new_rows_df
    if not new_rows_df.empty:
        if target_df.empty:
            updated_df = new_rows_df.copy()
        else:
            updated_df = pd.concat([target_df, new_rows_df], ignore_index=True, sort=False)
    else:
        updated_df = target_df.copy()  # No new rows, updated_df is just the original target

    # Ensure the final DataFrame has exactly the EXPECTED_TARGET_COLUMNS in the specified order
    # This will drop any columns not in EXPECTED_TARGET_COLUMNS and add any missing ones with NaN
    if not updated_df.empty:
        updated_df = updated_df.reindex(columns=current_expected_columns)
    else:  # If updated_df is empty (e.g. target was empty and no new rows)
        updated_df = pd.DataFrame(columns=current_expected_columns)

    num_rows_in_updated_df = len(updated_df)
    actual_new_rows_added_count = len(new_rows_list)  # Count of conceptually new rows

    try:
        updated_df.to_csv(target_csv_path, index=False, encoding="utf-8")

        if actual_new_rows_added_count > 0:
            logger.info(
                f"Successfully updated '{target_csv_path}', adding {actual_new_rows_added_count} new row(s). "
                f"Total rows: {num_rows_in_updated_df}."
            )
        elif not original_target_df_existed and num_rows_in_updated_df > 0:  # Created new file
            logger.info(f"Successfully created '{target_csv_path}' with {num_rows_in_updated_df} row(s) from source.")
        elif not original_target_df_existed and num_rows_in_updated_df == 0:  # Created new empty file
            logger.info(
                f"Successfully created empty '{target_csv_path}' with expected columns (source was also empty or had no new rows for an empty target)."
            )
        elif num_rows_in_updated_df == num_rows_in_original_target:  # Implies actual_new_rows_added_count was 0
            logger.info(
                f"No new unique rows to add. '{target_csv_path}' effectively unchanged (or only column structure enforced). "
                f"Total rows: {num_rows_in_updated_df}."
            )
        else:  # This case might occur if original target had more rows than updated, e.g. if it had duplicates by cluster_name that got implicitly handled by the logic, though current logic doesn't explicitly dedupe target.
            logger.info(
                f"Target CSV '{target_csv_path}' processed. Final row count: {num_rows_in_updated_df}. "
                f"Original had {num_rows_in_original_target} rows."
            )

    except OSError as e:
        logger.error(f"OS error writing CSV to '{target_csv_path}': {e}", exc_info=True)
        raise
    except Exception as e:
        logger.error(f"Error writing updated CSV to '{target_csv_path}': {e}", exc_info=True)
        raise


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Update a target CSV file with new rows from a source CSV file, keyed by 'cluster_name'.\n"
            "If a 'cluster_name' from source exists in target, the target row is kept as is.\n"
            "If a 'cluster_name' from source does not exist in target, a new row is added using source data.\n"
            "The target CSV will conform to the columns of the existing target file (if valid and contains 'cluster_name').\n"
            "If the target file is new, empty, or invalid, it will use the columns defined at DEFAULT_EXPECTED_TARGET_COLUMNS global variable to create the target CSV "
            "For new rows, 'platform_repository_revision' and 'workload_repository_revision' "
            "can be set to defaults or left blank."
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "source_csv",
        help="Path to the source CSV file (containing new data).",
    )
    parser.add_argument(
        "target_csv",
        help="Path to the target CSV file (to be updated, e.g., in Git).",
    )
    parser.add_argument(
        "--default-platform-revision",
        help="Default value for 'platform_repository_revision' for new cluster entries.",
        default=None,
    )
    parser.add_argument(
        "--default-workload-revision",
        help="Default value for 'workload_repository_revision' for new cluster entries.",
        default=None,
    )
    args = parser.parse_args()

    try:
        logger.info(f"Starting CSV update process: Source='{args.source_csv}', Target='{args.target_csv}'")
        update_csv_with_new_rows(
            args.source_csv, args.target_csv, args.default_platform_revision, args.default_workload_revision
        )
        logger.info("CSV update process finished successfully.")
    except FileNotFoundError as e:
        logger.error(f"File not found: {e}")
        sys.exit(1)
    except pd.errors.ParserError as e:
        logger.error(f"Error parsing CSV file: {e}")
        sys.exit(1)
    except ValueError as e:  # For missing 'cluster_name' or other validation
        logger.error(f"Validation error: {e}")
        sys.exit(1)
    except Exception as e:
        logger.critical(f"An unexpected error occurred: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
