import os
import argparse
import ast
import sys
import logging
from configparser import ConfigParser, Error as ConfigParserError
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
import pandas as pd
import requests
import google.auth
from google.auth.transport.requests import Request
from google.oauth2 import id_token
from google.auth.exceptions import GoogleAuthError
from requests.exceptions import RequestException, JSONDecodeError

# --- Setup Logging ---
logger = logging.getLogger(__name__)
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO").upper())

creds, auth_project = google.auth.default()

# --- Constants ---
CONFIG_FILE = "config.ini"
OUTPUT_INTENT_CSV = "eps_mock_cluster_intent_sot.csv"
OUTPUT_DATA_CSV = "eps_mock_cluster_data_sot.csv"

CONFIG_SECTIONS = {"SOT_COLUMNS": "sot_columns", "RENAME_COLUMNS": "rename_columns"}
CONFIG_OPTIONS = {"INTENT_COLS": "cluster_intent_sot", "DATA_COLS": "cluster_data_sot"}

# Prefixes to be removed from the key names of the flattened JSON DataFrame
PREFIXES_TO_REMOVE = ["data_", "intent_"]


# --- Load Configuration from the config file ---
def load_config(config_file: str) -> Optional[Dict[str, Any]]:
    """Loads and parses configuration from the specified INI file.

    Args:
        config_file: Path to the configuration file.

    Returns:
        A dictionary containing the parsed configuration, or None if an error occurs.
    """
    config = ConfigParser()
    try:
        if not config.read(config_file):
            print(
                f"Error: Configuration file '{config_file}' not found or empty.",
                file=sys.stderr,
            )
            return None

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
            print(f"Error parsing column lists in config: {e}", file=sys.stderr)
            return None
        rename_rules = {}
        # Get rename rules directly as a dictionary
        if config.has_section(CONFIG_SECTIONS["RENAME_COLUMNS"]):
            rename_rules = dict(config.items(CONFIG_SECTIONS["RENAME_COLUMNS"]))
        logging.info(f"Configuration loaded successfully from '{config_file}'.")
        return {
            "intent_columns": cluster_intent_cols,
            "data_columns": cluster_data_cols,
            "rename_rules": rename_rules,
        }

    except ConfigParserError as e:
        print(f"Error reading configuration file '{config_file}': {e}", file=sys.stderr)
        return None
    except Exception as e:  # Catch other potential errors like section/option not found
        print(
            f"An unexpected error occurred reading config '{config_file}': {e}",
            file=sys.stderr,
        )
        return None


@dataclass
class EPSParameters:
    client_id: str
    host: str


class EPSIntentReader:
    def __init__(self, host, client_id):
        self.host = host
        self.client_id = client_id

    def retrieve_source_of_truth(self):
        url = self._get_url()
        eps_json = make_iap_request(url, self.client_id)
        return eps_json

    def _get_url(self):
        return f"https://{self.host}/api/v1/clusters"


def get_parameters_from_environment():
    client_id = os.environ.get("EPS_CLIENT_ID")
    host = os.environ.get("EPS_HOST")

    if client_id is None:
        raise Exception("OAuth Client ID is Missing")
    if host is None:
        raise Exception("EPS HOST URL is not Set")

    return EPSParameters(client_id=client_id, host=host)


# --- IAP Request Function ---
def make_iap_request(url: str, client_id: str, method: str = "GET", **kwargs) -> str:
    """Makes a request to an application protected by Identity-Aware Proxy.

    Args:
      url: The Identity-Aware Proxy-protected URL to fetch.
      client_id: The client ID used by Identity-Aware Proxy.
      method: The request method to use.
      **kwargs: Any parameters for requests.request.

    Returns:
      The page body text.

    Raises:
        Exception: If the request fails or returns a non-200 status.
    """
    if "timeout" not in kwargs:
        kwargs["timeout"] = 90

    try:
        open_id_connect_token = id_token.fetch_id_token(Request(), client_id)

        resp = requests.request(
            method,
            url,
            headers={"Authorization": f"Bearer {open_id_connect_token}"},
            **kwargs,
        )

        resp.raise_for_status()  # Raises HTTPError for bad responses (4xx or 5xx)
        try:
            return resp.json()
        except JSONDecodeError as json_err:
            logging.error(
                f"Failed to decode JSON response from {url}. Response text: {resp.text[:500]}..."
            )  # Log part of the response
            raise Exception(f"Invalid JSON response received from {url}") from json_err

    except (GoogleAuthError, RequestException) as e:
        logging.error(f"Error making IAP request to {url}: {e}", exc_info=True)
        raise Exception(f"IAP request failed: {e}") from e
    except Exception as e:
        logging.exception(f"An unexpected error occurred during IAP request to {url}")
        # Re-raise or handle as appropriate for the application context
        raise Exception(f"IAP request failed: {e}") from e


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
            return text[len(prefix) :]
    return text


def process_data(
    data: Dict, prefixes_to_remove: List[str], rename_rules: Dict[str, str]
) -> Optional[pd.DataFrame]:
    """Flattens JSON data, removes prefixes, and renames columns.

    Args:
        data: The raw data dictionary (expected to have a 'clusters' key).
        prefixes_to_remove: List of prefixes to remove from column names.
        rename_rules: Specific column renaming rules (original_name: new_name).

    Returns:
        A processed Pandas DataFrame, or None if 'clusters' key is missing.
    """
    if "clusters" not in data:
        print("Error: 'clusters' key not found in the input data.", file=sys.stderr)
        return None

    try:
        flattened_df = pd.json_normalize(data["clusters"], sep="_")
        # Apply prefix removal
        prefix_rename_map = {
            col: remove_prefix_any(col, prefixes_to_remove)
            for col in flattened_df.columns
        }
        flattened_df.rename(columns=prefix_rename_map, inplace=True)

        # Apply specific renaming rules from config
        # Filter rename_rules to only include columns present after prefix removal
        current_columns = set(flattened_df.columns)
        effective_rename_rules = {
            k: v for k, v in rename_rules.items() if k in current_columns
        }

        flattened_df.rename(columns=effective_rename_rules, inplace=True)
        logging.info(f"Final column rename mapping applied: {effective_rename_rules}")
        return flattened_df

    except Exception as e:
        print(f"Error processing data: {e}", file=sys.stderr)
        return None


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
            print(
                f"Warning: The following columns were requested but not found in the data for '{output_filename}': {missing_cols}",
                file=sys.stderr,
            )
            # Filter columns to only include those that actually exist
            columns = [col for col in columns if col in df.columns]
            if not columns:
                print(
                    f"Error: No valid columns found to generate '{output_filename}'. Skipping.",
                    file=sys.stderr,
                )
                return

        df_subset = df[columns]
        df_subset.to_csv(output_filename, index=False, encoding="utf-8")
        logging.info(f"Successfully generated '{output_filename}'")
    except KeyError as e:
        print(
            f"Error: Column {e} not found while generating '{output_filename}'.",
            file=sys.stderr,
        )
    except Exception as e:
        print(f"Error generating CSV file '{output_filename}': {e}", file=sys.stderr)


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
    params = get_parameters_from_environment()

    # Check if any action is requested
    print("checking if any action is requested...")
    if not args.cluster_intent_sot and not args.cluster_data_sot:
        print("No action specified. Use -intent or -data flag to generate CSV files.")
        parser.print_help()
        sys.exit(0)  # Exit gracefully if no action requested

    # Load Configuration
    config_data = load_config(CONFIG_FILE)
    if not config_data:
        sys.exit(1)  # Exit if config loading failed

    # Fetch the Source of Truth from EPS
    intent_reader = EPSIntentReader(params.host, params.client_id)
    raw_data = intent_reader.retrieve_source_of_truth()
    if not raw_data:
        sys.exit(1)  # Exit if data loading failed

    # Process Data
    processed_df = process_data(
        raw_data, PREFIXES_TO_REMOVE, config_data["rename_rules"]
    )
    if processed_df is None:
        sys.exit(1)  # Exit if data processing failed

    # Generate Outputs based on arguments
    if args.cluster_intent_sot:
        generate_csv(processed_df, config_data["intent_columns"], OUTPUT_INTENT_CSV)

    if args.cluster_data_sot:
        generate_csv(processed_df, config_data["data_columns"], OUTPUT_DATA_CSV)


if __name__ == "__main__":
    main()
