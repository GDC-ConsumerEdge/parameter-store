import argparse
import ast
import logging
import os
import sys
from collections import Counter
from configparser import ConfigParser, Error as ConfigParserError
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Any
import google.auth
import google.oauth2.credentials
import pandas as pd
from google.auth.exceptions import GoogleAuthError  # Specific exceptions
from google.auth.transport.requests import AuthorizedSession
from google.cloud import iam_credentials_v1
from requests.exceptions import (
    RequestException,
    JSONDecodeError,
    HTTPError,
)  # Specific exceptions

# --- Setup Logging ---
logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

# --- Constants ---
SCRIPT_DIR = Path(__file__).parent.resolve()
CONFIG_FILE = os.environ.get("CONFIG_INI_PATH", SCRIPT_DIR / "config.ini")
OUTPUT_INTENT_CSV = os.environ.get(
    "OUTPUT_INTENT_CSV", "cluster_intent_sot.csv"
)  # Matching the file path of SoT files in  GitHub Repositories
OUTPUT_DATA_CSV = os.environ.get(
    "OUTPUT_DATA_CSV", "source_of_truth.csv"
)  # Matching the file path in GitHub Repositories

# Define expected section and option names in the config file
CONFIG_SECTIONS = {"SOT_COLUMNS": "sot_columns", "RENAME_COLUMNS": "rename_columns"}
CONFIG_OPTIONS = {"INTENT_COLS": "cluster_intent_sot", "DATA_COLS": "cluster_data_sot"}

# Prefixes used in the source EPS API JSON response to distinguish between intent and data fields
INTENT_PREFIX = "intent_"
DATA_PREFIX = "data_"


# --- Load Configuration from the config file ---
def load_config(config_file: str) -> Dict[str, Any]:
    """Loads and parses configuration from the specified INI file.

    Args:
        config_file: Path to the configuration file.

    Returns:
        A dictionary containing the parsed configuration

    Raises:
        FileNotFoundError: If the config file doesn't exist or isn't readable.
        ConfigParserError: If there's an issue parsing the INI structure.
        ValueError: If list parsing fails or sections/options are missing.
    """
    config = ConfigParser()
    try:
        if not config.read(config_file):
            raise FileNotFoundError(
                f"Configuration file '{config_file}' not found or couldn't be read"
            )

        # Safely parse list-like strings from config
        try:
            cluster_intent_cols = ast.literal_eval(
                config.get(
                    CONFIG_SECTIONS["SOT_COLUMNS"], CONFIG_OPTIONS["INTENT_COLS"]
                )
            )
            cluster_data_cols = ast.literal_eval(
                config.get(CONFIG_SECTIONS["SOT_COLUMNS"], CONFIG_OPTIONS["DATA_COLS"])
            )
        except (SyntaxError, ValueError) as e:
            raise ValueError(f"Error parsing column lists in config: {e}") from e
        except (ConfigParserError, KeyError) as e:
            raise ValueError(
                f"Missing section/option in config file '{config_file}': {e}"
            ) from e

        # Get rename rules directly as a dictionary
        rename_rules = (
            dict(config.items(CONFIG_SECTIONS["RENAME_COLUMNS"]))
            if config.has_section(CONFIG_SECTIONS["RENAME_COLUMNS"])
            else {}
        )

        logger.info(f"Configuration loaded successfully from '{config_file}'.")
        return {
            "intent_columns": cluster_intent_cols,
            "data_columns": cluster_data_cols,
            "rename_rules": rename_rules,
        }
    except ConfigParserError as e:
        raise ConfigParserError(
            f"Error reading configuration file '{config_file}': {e}"
        ) from e


@dataclass
class EPSParameters:
    """Simple data class to hold parameters needed for EPS API."""
    eps_oauth_client_id: str
    host: str
    service_account: str


def retrieve_eps_source_of_truth(params: EPSParameters) -> Dict:
    """Retrieves the source of truth data from the EPS API.

    Args:
        params: An EPSParameters object containing API connection details.

    Returns:
        A dictionary representing the JSON response from the EPS API.

    Raises:
        Propagates exceptions from make_iap_request (e.g., RequestException, ValueError, GoogleAuthError).
    """
    # Construct the target API endpoint URL
    url = f"https://{params.host}/api/v1/clusters"
    logger.info(f"Retrieving Source of Truth from: {url}")
    # Delegate the actual API request
    eps_json = make_iap_request(url, params.eps_oauth_client_id, params.service_account)
    return eps_json


def get_parameters_from_environment() -> EPSParameters:
    """Retrieves required parameters from environment variables.

    Returns:
        An EPSParameters object containing the parameters.

    Raises:
        ValueError: If any required environment variable is missing.
    """
    eps_oauth_client_id = os.environ.get("EPS_CLIENT_ID")
    host = os.environ.get("EPS_HOST")
    service_account = os.environ.get("SERVICE_ACCOUNT")

    missing_vars = []
    if eps_oauth_client_id is None:
        missing_vars.append("EPS_CLIENT_ID")
    if host is None:
        missing_vars.append("EPS_HOST")
    if service_account is None:
        missing_vars.append("SERVICE_ACCOUNT")

    if missing_vars:
        # Raise ValueError for configuration issues
        raise ValueError(
            f"Missing required environment variables: {', '.join(missing_vars)}"
        )

    logger.info("Successfully retrieved parameters from environment variables.")
    return EPSParameters(
        eps_oauth_client_id=eps_oauth_client_id,
        host=host,
        service_account=service_account,
    )


# --- IAP Request Function ---
def make_iap_request(
    url: str,
    eps_oauth_client_id: str,
    service_account: str,
    method: str = "GET",
    **kwargs,
) -> Dict:
    """Makes a request to an application protected by Identity-Aware Proxy.

    Args:
      method: The HTTP method to make the request (default: "GET"). EPS supports only GET as of now so only that is implemented.
      service_account: The Target Service Account Email to be impersonated.
      url: The Identity-Aware Proxy-protected URL to fetch.
      eps_oauth_client_id: The client ID used by Identity-Aware Proxy for the target app.
      **kwargs: Any additional parameters for requests.request.

    Returns:
      The parsed JSON response body as a dictionary.

    Raises:
        NotImplementedError: If method != GET (other methods can be implemented later)
        ValueError: If the response is not valid JSON.
        GoogleAuthError: If there's an issue with Google authentication or token generation.
        RequestException: For network-related errors during the request.
        Exception: If the request fails or returns a non-200 status.
    """
    # Currently, only GET is supported by EPS API and hence, only it is implemented. Extend this if needed in the future.
    if method.upper() != "GET":
        logger.error(f"HTTP method '{method}' not currently supported.")
        raise NotImplementedError(f"HTTP method '{method}' not implemented.")
    #Default timeout of 90 seconds for the request
    kwargs.setdefault("timeout", 90)

    try:
        target_service_account_email = service_account
        audience = eps_oauth_client_id
        logger.debug(
            f"Generating ID token for SA '{target_service_account_email}' with audience '{audience}'"
        )
        client = iam_credentials_v1.IAMCredentialsClient()
        name = f"projects/-/serviceAccounts/{target_service_account_email}"
        id_token_response = client.generate_id_token(
            name=name, audience=audience, include_email=True
        )
        id_token_jwt = id_token_response.token # Extract the actual signed JWT token
        logger.debug("Creating authorized session with generated ID token.")
        iap_creds = google.oauth2.credentials.Credentials(id_token_jwt)
        # Create an authorized session object that already includes the token in headers
        authed_session = AuthorizedSession(iap_creds)
        # Make the HTTP request using the authorized session
        logger.info(f"Making {method} request to IAP URL: {url}")

        resp = authed_session.request(method, url, **kwargs)
        logger.info(f"Received status code: {resp.status_code} from {url}")
        try:
            resp.raise_for_status()  # Raises HTTPError for bad responses (4xx or 5xx)
        except HTTPError as e:
            logger.error(
                f"Got http response status code: {resp.status_code} ", exc_info=True
            )
            raise HTTPError(
                f"Received a {resp.status_code} http response code on making HTTP request to EPS"
            ) from e

        try:
            return resp.json()
        except JSONDecodeError as json_err:
            logger.error(
                f"Failed to decode JSON response from {url}. Response text: {resp.text[:500]}..."
            )  # Log part of the response
            raise ValueError(f"Invalid JSON response received from {url}") from json_err
    except (GoogleAuthError, RequestException) as e:
        logger.error(f"Error making IAP request to {url}: {e}", exc_info=True)
        raise
    except Exception as e:
        logger.exception(
            f"An unexpected error occurred during IAP request to {url}: {e}"
        )
        raise


def process_data(data: Dict, mode: str, rename_rules: Dict[str, str]) -> pd.DataFrame:
    """
    Processes the raw data fetched from EPS for a specific mode ('intent' or 'data').

    Steps:
    1. Flattens the nested JSON structure (specifically the 'clusters' list).
    2. Filters columns, keeping only those relevant to the specified `mode` (intent or data)
    3. Removes the mode-specific prefix (e.g : 'intent_') from column names.
       Handles conflicts: If removing the prefix results in a name that already
       exists as a non-prefixed column, the original prefixed name is kept.
    4. Handles any remaining duplicate column names (e.g : from source data),
       keeping the first occurrence.
    5. Validates and applies the `rename_rules` provided in the config.

    Args:
        data: The raw data dictionary fetched from EPS (expected to have a root 'clusters' key containing a list).
        mode: The processing mode ('intent' or 'data').
        rename_rules: Dictionary mapping source column names to target column names.

    Returns:
        A processed Pandas DataFrame ready for CSV generation.

    Raises:
        ValueError: If input data is invalid, mode is incorrect, or rename rules conflict.
        Exception: For unexpected errors during processing.
    """
    if "clusters" not in data:
        raise ValueError("Input data is missing the required 'clusters' key.")
    if mode not in ["intent", "data"]:
        raise ValueError(f"Invalid mode specified: {mode}. Must be 'intent' or 'data'.")

    logger.info(f"Starting data processing for mode: '{mode}'")

    try:
        # 1. Flatten the data
        flattened_df = pd.json_normalize(data["clusters"], sep="_")
        logger.debug(
            f"Initial columns after flattening: {flattened_df.columns.tolist()}"
        )

        # 2. Filter columns based on mode
        prefix_to_keep = INTENT_PREFIX if mode == "intent" else DATA_PREFIX
        prefix_to_discard = DATA_PREFIX if mode == "intent" else INTENT_PREFIX
        
        # Keep columns that DO NOT start with the prefix of the OTHER mode.
        # This implicitly keeps columns starting with the current mode's prefix AND columns without any prefix.
        # for e.g : if mode is "intent", then all the columns with "data_" as the prefix are discarded
        cols_to_keep = [
            col for col in flattened_df.columns if not col.startswith(prefix_to_discard)
        ]

        if not cols_to_keep:
            logger.warning(
                f"No columns found matching the criteria for mode '{mode}'. Returning empty DataFrame."
            )
            return pd.DataFrame()

        flattened_df = flattened_df[cols_to_keep]
        original_filtered_columns = (
            flattened_df.columns.tolist()
        )  # Store columns before prefix removal
        logger.debug(
            f"Columns after mode filtering ('{mode}'): {original_filtered_columns}"
        )

        # 3. Build rename map for prefix removal, handling conflicts with existing non-prefixed columns
        final_rename_map = {}
        columns_after_filtering_set = set(
            original_filtered_columns
        )  # For faster lookups

        for col in original_filtered_columns:
            if col.startswith(prefix_to_keep):
                base_name = col[len(prefix_to_keep) :]
                # Check if the target base_name already exists as another column
                if base_name in columns_after_filtering_set:
                    # Conflict detected! Keep the original prefixed name.
                    # Not adding an entry to final_rename_map for this column.
                    logger.info(
                        f"Conflict detected for mode '{mode}': Column '{col}' target name '{base_name}' "
                        f"collides with existing column. Keeping original column name '{col}'."
                    )
                    # Continue to the next column without adding a rename rule for 'col'
                    continue
                else:
                    final_rename_map[col] = base_name

        # Apply the calculated renames (only non-conflicting ones)
        if final_rename_map:
            flattened_df.rename(columns=final_rename_map, inplace=True)
            logger.debug(
                f"Columns after prefix removal/conflict resolution ('{mode}'): {flattened_df.columns.tolist()}"
            )
        else:
            logger.info(f"No non-conflicting prefix removals needed for mode '{mode}'.")

        #  Handle duplicates already present in source JSON after flattening. First occurence is kept assuming the data is the same in both the fields.
        cols_after_rename = flattened_df.columns
        if cols_after_rename.has_duplicates:
            duplicate_mask = cols_after_rename.duplicated(keep="first")
            keep_mask = ~duplicate_mask
            remaining_duplicate_names = (
                cols_after_rename[cols_after_rename.duplicated(keep=False)]
                .unique()
                .tolist()
            )

            if remaining_duplicate_names:
                logger.warning(
                    f"Duplicate column names still found after prefix handling for mode '{mode}': {remaining_duplicate_names}. "
                    f"These likely originated from the source data. Keeping the first occurrence of each."
                )
                flattened_df = flattened_df.loc[:, keep_mask]
                logger.debug(
                    f"Columns after handling remaining duplicates ('{mode}'): {flattened_df.columns.tolist()}"
                )

        # Validate and apply specific rename_rules
        current_columns = set(flattened_df.columns)
        effective_rename_rules = {}
        target_name_counts = Counter(rename_rules.values())
        logger.debug(f"Validating specific rename rules for mode '{mode}'...")
        for original_name, new_name in rename_rules.items():
            # skip the column from rename_rules if it doesn't exist in the dataframe
            if original_name not in current_columns:
                logger.warning(
                    f"Rename rule '{original_name}' -> '{new_name}' skipped: Column '{original_name}' not found"
                )
                continue

            # Check if there's a conflict of target_column name to be renamed to, with existing dataframe column name
            if new_name in current_columns and new_name != original_name:
                raise ValueError(
                    f"Invalid rename_rules for mode '{mode}': Rule '{original_name}' -> '{new_name}' "
                    f"conflicts with existing column '{new_name}'."
                )
            # Check for conflict with another rename rule's target
            if target_name_counts[new_name] > 1:
                conflicting_originals = [
                    k
                    for k, v in rename_rules.items()
                    if v == new_name and k != original_name
                ]
                raise ValueError(
                    f"Invalid rename_rules for mode '{mode}': Multiple rules target the same name '{new_name}'. "
                    f"(Conflicts involve original columns: {conflicting_originals})"
                )
            effective_rename_rules[original_name] = new_name

        # Apply the filtered renaming rules
        if effective_rename_rules:
            logger.info(
                f"Applying specific column renames for mode '{mode}': {effective_rename_rules}"
            )
            flattened_df.rename(columns=effective_rename_rules, inplace=True)
        else:
            logger.info(
                f"No specific column rename rules were applicable for mode '{mode}'."
            )

        logger.info(f"Data processing completed successfully for mode '{mode}'.")
        return flattened_df

    except Exception as e:
        logger.exception(f"Error processing data for mode '{mode}': {e}")
        # Re-raise the exception to be caught by the main try-except block with more context
        raise Exception(f"Failed during data processing for mode '{mode}': {e}") from e


def generate_csv(df: pd.DataFrame, columns: List[str], output_filename: str):
    """Generates a CSV file from selected columns of a DataFrame.

    Args:
        df: The Pandas DataFrame.
        columns: A list of column names to include in the CSV.
        output_filename: The name for the output CSV file.
    """
    try:
        # Check if all requested columns exist
        missing_cols = [col for col in columns if col not in df.columns]
        if missing_cols:
            logger.warning(
                f"The following requested columns were not found in the data for '{output_filename}': {missing_cols}"
            )
            # Filter requested columns to only include those that actually exist in the data frame
            columns = [col for col in columns if col in df.columns]
            if not columns:
                logger.error(
                    f"No valid columns found to generate '{output_filename}'. Skipping."
                )
                return

        df_subset = df[columns]
        df_subset.to_csv(output_filename, index=False, encoding="utf-8")
        logger.info(f"Successfully generated '{output_filename}'")
    except KeyError as e:
        logger.error(
            f"Column '{e}' not found while generating '{output_filename}'.",
        )
        raise
    except OSError as e:  # Catch potential directory creation or file writing errors
        logger.error(f"OS error during CSV generation for '{output_filename}': {e}")
        raise
    except Exception as e:
        logger.exception(f"Error generating CSV file '{output_filename}': {e}")
        raise


# --- Main Execution ---
def main():
    """Main function to parse arguments, load data, process, and generate CSVs."""
    parser = argparse.ArgumentParser(
        description="Generate Cluster SoT CSV files from EPS data."
    )
    parser.add_argument(
        "-intent",
        "--cluster-intent-sot",
        help="Generate Cluster Intent SoT CSV File",
        action="store_true",
    )
    parser.add_argument(
        "-data",
        "--cluster-data-sot",
        help="Generate Cluster Data SoT CSV File",
        action="store_true",
    )
    args = parser.parse_args()
    try:

        # Check if atleast one action (intent or data) is requested
        logger.info("Checking requested actions...")
        if not args.cluster_intent_sot and not args.cluster_data_sot:
            logger.info(
                "No action specified. Use -intent or -data flag to generate CSV files."
            )
            parser.print_help(file=sys.stdout)
            sys.exit(0)  # Exit gracefully if no action requested
        logger.info("Attempting Google Cloud authentication...")
        # Attempt to authenticate with Google Cloud using Application Default Credentials (ADC)
        try:
            creds, auth_project = (
                google.auth.default()
            )  # GOOGLE_APPLICATION_CREDENTIALS
            logger.debug(f"Loaded credential type: {type(creds)}")
            if auth_project:
                logger.debug(f"Authenticated with project: {auth_project}")
            logger.info("Google Cloud authentication successful.")
        except GoogleAuthError as auth_err:
            logger.critical(
                f"Google Cloud Authentication failed: {auth_err}", exc_info=True
            )
            sys.exit(1)

        params = get_parameters_from_environment()
        # Load Configuration
        config_data = load_config(CONFIG_FILE)

        # Fetch the Source of Truth from EPS
        raw_data = retrieve_eps_source_of_truth(params)
        if not raw_data:
            logger.critical("Failed to retrieve data from EPS. Exiting.")
            sys.exit(1)  # Exit if data loading failed

        # --- Process and Generate CSV based on arguments ---
        if args.cluster_intent_sot:
            logger.info("--- Processing for Intent SoT ---")
            intent_df = process_data(
                raw_data, mode="intent", rename_rules=config_data["rename_rules"]
            )
            if not intent_df.empty:
                logger.info("Generating Cluster Intent SoT CSV...")
                generate_csv(
                    intent_df, config_data["intent_columns"], OUTPUT_INTENT_CSV
                )
            else:
                logger.warning(
                    f"Skipping generation of '{OUTPUT_INTENT_CSV}' due to empty processed data."
                )

        if args.cluster_data_sot:
            logger.info("--- Processing for Data SoT ---")
            data_df = process_data(
                raw_data, mode="data", rename_rules=config_data["rename_rules"]
            )
            if not data_df.empty:
                logger.info("Generating Cluster Data SoT CSV...")
                generate_csv(data_df, config_data["data_columns"], OUTPUT_DATA_CSV)
            else:
                logger.warning(
                    f"Skipping generation of '{OUTPUT_DATA_CSV}' due to empty processed data."
                )

        logger.info("Script finished successfully.")
    except (FileNotFoundError, ValueError, ConfigParserError) as e:
        logger.critical(f"Configuration or Data Error: {e}")
        sys.exit(1)
    except (GoogleAuthError, RequestException) as e:
        logger.critical(f"API Request Error: {e}")
        sys.exit(1)
    except Exception as e:
        logger.critical(f"An unexpected critical error occurred: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
