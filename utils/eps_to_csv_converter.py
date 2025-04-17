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
from google.auth.exceptions import GoogleAuthError  # Specific exception
from google.auth.transport.requests import AuthorizedSession
from google.cloud import iam_credentials_v1
from requests.exceptions import RequestException, JSONDecodeError  # Specific exceptions

# --- Setup Logging ---
logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

creds, auth_project = google.auth.default()  # GOOGLE_APPLICATION_CREDENTIALS
logger.debug(f"Loaded credential type: {type(creds)}")
if auth_project:
    logger.debug(f"Authenticated with project: {auth_project}")

# --- Constants ---
SCRIPT_DIR = Path(__file__).parent.resolve()
CONFIG_FILE = SCRIPT_DIR / "config.ini"
OUTPUT_INTENT_CSV = os.environ.get(
    "OUTPUT_INTENT_CSV", "cluster_intent_sot.csv"
)  # Matching the file path of SoT files in  GitHub Repositories
OUTPUT_DATA_CSV = os.environ.get(
    "OUTPUT_DATA_CSV", "source_of_truth.csv"
)  # Matching the file path in GitHub Repositories

CONFIG_SECTIONS = {"SOT_COLUMNS": "sot_columns", "RENAME_COLUMNS": "rename_columns"}
CONFIG_OPTIONS = {"INTENT_COLS": "cluster_intent_sot", "DATA_COLS": "cluster_data_sot"}

# Prefixes to be removed from the key names of the flattened JSON DataFrame
PREFIXES_TO_REMOVE = ["data_", "intent_"]


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
    client_id: str
    host: str
    service_account: str


def retrieve_eps_source_of_truth(params: EPSParameters) -> Dict:
    """Retrieves the source of truth data from the EPS API."""
    url = f"https://{params.host}/api/v1/clusters"
    logger.info(f"Retrieving Source of Truth from: {url}")
    # Pass parameters directly to the request function
    eps_json = make_iap_request(url, params.client_id, params.service_account)
    return eps_json


def get_parameters_from_environment() -> EPSParameters:
    """Retrieves required parameters from environment variables.

    Returns:
        An EPSParameters object containing the parameters.

    Raises:
        ValueError: If any required environment variable is missing.
    """
    client_id = os.environ.get("EPS_CLIENT_ID")
    host = os.environ.get("EPS_HOST")
    service_account = os.environ.get("SERVICE_ACCOUNT")

    missing_vars = []
    if client_id is None:
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
        client_id=client_id, host=host, service_account=service_account
    )


# --- IAP Request Function ---
def make_iap_request(
        url: str, client_id: str, service_account: str, method: str = "GET", **kwargs
) -> Dict:
    """Makes a request to an application protected by Identity-Aware Proxy.

    Args:
      method: The HTTP method to make the request
      service_account: The Target Service Account Email to be impersonated
      url: The Identity-Aware Proxy-protected URL to fetch.
      client_id: The client ID used by Identity-Aware Proxy.
      **kwargs: Any parameters for requests.request.

    Returns:
      The parsed JSON response body as a dictionary.

    Raises:
        NotImplementedError: If method != GET (other methods can be implemented later)
        ValueError: If the response is not valid JSON.
        Exception: If the request fails or returns a non-200 status.
    """
    if method.upper() != "GET":  # Added method handling example
        logger.error(f"HTTP method '{method}' not currently supported.")
        raise NotImplementedError(f"HTTP method '{method}' not implemented.")

    if "timeout" not in kwargs:
        kwargs["timeout"] = 90

    try:
        target_service_account_email = service_account
        audience = client_id
        logger.debug(
            f"Generating ID token for SA '{target_service_account_email}' with audience '{audience}'"
        )
        client = iam_credentials_v1.IAMCredentialsClient()
        name = f"projects/-/serviceAccounts/{target_service_account_email}"
        id_token_response = client.generate_id_token(
            name=name, audience=audience, include_email=True
        )
        id_token_jwt = id_token_response.token
        logger.debug("Creating authorized session with generated ID token.")
        iap_creds = google.oauth2.credentials.Credentials(id_token_jwt)
        authed_session = AuthorizedSession(iap_creds)

        logger.info(f"Making {method} request to IAP URL: {url}")

        resp = authed_session.request(method, url, **kwargs)
        logger.info(f"Received status code: {resp.status_code} from {url}")
        resp.raise_for_status()  # Raises HTTPError for bad responses (4xx or 5xx)
        try:
            return resp.json()
        except JSONDecodeError as json_err:
            logger.error(
                f"Failed to decode JSON response from {url}. Response text: {resp.text[:500]}..."
            )  # Log part of the response
            raise ValueError(f"Invalid JSON response received from {url}") from json_err
    except (GoogleAuthError, RequestException) as e:
        logger.error(f"Error making IAP request to {url}: {e}", exc_info=True)
        raise e
    except Exception as e:
        logger.exception(f"An unexpected error occurred during IAP request to {url}")
        # Re-raise or handle as appropriate for the application context
        raise e


def remove_prefix_any(text: str, prefixes: List[str]) -> str:
    """Removes the first matching prefix from a string.

    Args:
        text: The input string.
        prefixes: A list of prefixes to check for.

    Returns:
        The string with the first matching prefix removed, or the original string.
    """
    for prefix in prefixes:
        if text.startswith(prefix):
            return text[len(prefix):]
    return text


def process_data(
        data: Dict, prefixes_to_remove: List[str], rename_rules: Dict[str, str]
) -> pd.DataFrame:
    """Flattens JSON data, removes prefixes, handles duplicated column names scenarios, validates rename_rules and
    renames columns.

    Args:
        data: The raw data dictionary (expected to have a 'clusters' key).
        prefixes_to_remove: List of prefixes to remove from column names.
        rename_rules: Specific column renaming rules (original_name: new_name).

    Returns:
        A processed Pandas DataFrame

    Raises:
        ValueError: If the input data is invalid.
        Exception: For unexpected errors during processing.
    """
    if "clusters" not in data:
        raise ValueError("Input data is missing the required 'clusters' key.")

    try:
        flattened_df = pd.json_normalize(data["clusters"], sep="_")
        logger.debug(f"Initial columns after flattening: {flattened_df.columns.tolist()}")
        # Apply prefix removal
        prefix_rename_map = {
            col: remove_prefix_any(col, prefixes_to_remove)
            for col in flattened_df.columns
        }
        flattened_df.rename(columns=prefix_rename_map, inplace=True)
        logger.debug(f"Columns after prefix removal: {flattened_df.columns.tolist()}")

        # handle potential duplicate columns caused by prefix removal
        cols_after_prefix = flattened_df.columns
        if cols_after_prefix.has_duplicates:
            duplicate_mask = cols_after_prefix.duplicated(keep="first")
            keep_mask = ~duplicate_mask
            all_duplicate_occurrences_mask = cols_after_prefix.duplicated(keep=False)
            duplicate_col_names = cols_after_prefix[all_duplicate_occurrences_mask].unique().tolist()
            logger.warning(
                f"Duplicate column names found after prefix removal: {duplicate_col_names}. "
                f"Keeping the first occurrence of each."
            )
            # Select only the columns marked to keep (first occurrences)
            flattened_df = flattened_df.loc[:, keep_mask]

        # 3. Validate specific renaming rules BEFORE applying them
        current_columns = set(flattened_df.columns)
        effective_rename_rules = {}
        target_name_counts = Counter(rename_rules.values())
        logger.debug("Validating specific rename rules...")
        for original_name, new_name in rename_rules.items():
            if original_name not in current_columns:
                continue
                # Check if there's a conflict with existing column
            if new_name in current_columns and new_name != original_name:
                raise ValueError(
                    f"Invalid rename_rules: Rule '{original_name}' -> '{new_name}' "
                    f"conflicts with existing column '{new_name}'."
                )
                # Check for conflict with another rename rule's target
            if target_name_counts[new_name] > 1:
                conflicting_originals = [k for k, v in rename_rules.items() if v == new_name and k != original_name]
                raise ValueError(
                    f"Invalid rename_rules: Multiple rules target the same name '{new_name}'. "
                    f"(Conflicts: '{original_name}' and {conflicting_originals})"
                )
            effective_rename_rules[original_name] = new_name

        # Apply the final renaming rules
        # Filter rename_rules to only include columns present after prefix removal
        if effective_rename_rules:
            logger.info(f"Applying specific column renames: {effective_rename_rules}")
            flattened_df.rename(columns=effective_rename_rules, inplace=True)
        else:
            logger.info("No specific column rename rules matched current columns.")
        logger.info("Data processing completed successfully.")
        return flattened_df

    except Exception as e:
        logger.exception(f"Error processing data: {e}")
        raise Exception(f"Failed during data processing: {e}") from e


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
            # Filter columns to only include those that actually exist
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
        params = get_parameters_from_environment()

        # Check if any action is requested
        logger.info("Checking requested actions...")
        if not args.cluster_intent_sot and not args.cluster_data_sot:
            logger.info(
                "No action specified. Use -intent or -data flag to generate CSV files."
            )
            parser.print_help(file=sys.stdout)
            sys.exit(0)  # Exit gracefully if no action requested

        # Load Configuration
        config_data = load_config(CONFIG_FILE)

        # Fetch the Source of Truth from EPS
        raw_data = retrieve_eps_source_of_truth(params)
        if not raw_data:
            logger.critical("Failed to retrieve data from EPS. Exiting.")
            sys.exit(1)  # Exit if data loading failed

        # Process Data
        processed_df = process_data(
            raw_data, PREFIXES_TO_REMOVE, config_data["rename_rules"]
        )

        # Generate Outputs based on arguments
        if args.cluster_intent_sot:
            logger.info("Generating Cluster Intent SoT CSV...")
            generate_csv(processed_df, config_data["intent_columns"], OUTPUT_INTENT_CSV)

        if args.cluster_data_sot:
            logger.info("Generating Cluster Data SoT CSV...")
            generate_csv(processed_df, config_data["data_columns"], OUTPUT_DATA_CSV)

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
