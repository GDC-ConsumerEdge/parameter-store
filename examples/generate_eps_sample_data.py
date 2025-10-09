#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "click",
#     "faker",
#     "faker-airtravel",
# ]
# ///

# Copyright 2025 Google, LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import csv
import os
import random

import click
from faker import Faker
from faker_airtravel import AirTravelProvider

fake = Faker()
fake.add_provider(AirTravelProvider)

# If needed, this value can be changed to an arbitrarily high value.
# The default is a 16-bit int
max_cluster_count = 65534


@click.command(context_settings={"show_default": True})
@click.option(
    "-c",
    "--cluster-count",
    type=int,
    default=100,
    help=f"The number of random GDC clusters to create. Values up to {max_cluster_count} are accepted",
)
@click.option(
    "-n",
    "--organization-name",
    type=str,
    default="Example Org",
    help="An organization name to be used for these clusters",
)
@click.option(
    "-o",
    "--output-file-suffix",
    type=str,
    default="sample.csv",
    help="Write resulting CSV files with this suffix",
)
@click.option(
    "--overwrite",
    is_flag=True,
    default=False,
    help="If previously generated CSV files are already present, overwrite them",
)
def generate_eps_data(cluster_count: int, organization_name: str, output_file_suffix: str, overwrite: bool):
    """Generates sample data for the Parameter Store Application.
    \f  # Click truncation marker

    Args:
        cluster_count (int): The number of example clusters to be created.
        organization_name (str): A real or fictional organizational name to be used in the sample data.
        output_file_suffix (str): A suffix to be used for the resulting output files.
        overwrite (bool): If the resulting output files already exist, should they be overwriten.
    """

    validate_user_options(cluster_count=cluster_count)

    # Make sure any user-defined output suffixes have a .csv file extension
    if ".csv" not in output_file_suffix:
        output_file_suffix = f"{output_file_suffix}.csv"

    click.confirm(
        f"Generating {cluster_count} random cluster intent entries for {organization_name} into {output_file_suffix}\nDo you want to continue?",
        abort=True,
    )

    generated_csv_data = {
        "cluster_intent": [],
        "cluster_registry": [],
        "platform": [],
        "workload": [],
    }

    # Validate if the resulting output file exists before generating new data
    for i in generated_csv_data.keys():
        validate_user_options(output_file=f"{i}_{output_file_suffix}", overwrite=overwrite)

    # Sample country codes, their relative weighting and other country-specific sample data
    country_codes = {
        "us": {"weight": 5, "gcp_region": "us-central1", "lb_ips": "192.168.10.0/24"},
        "ca": {"weight": 2, "gcp_region": "northamerica-northeast2", "lb_ips": "192.168.25.0/24"},
        "gb": {"weight": 5, "gcp_region": "europe-west2", "lb_ips": "192.168.40.0/24"},
        "de": {"weight": 3, "gcp_region": "europe-west3", "lb_ips": "192.168.55.0/24"},
        "it": {"weight": 1, "gcp_region": "europe-west8", "lb_ips": "192.168.70.0/24"},
        "es": {"weight": 3, "gcp_region": "europe-west9", "lb_ips": "192.168.85.0/24"},
    }
    environments = ["dev", "staging", "prod"]
    max_store_id_range = max_cluster_count
    max_zone_id_range = max_cluster_count
    # Tags will be similar to 'function', 'portal', 'structure', 'core', 'utilization'
    cluster_tags = [fake.catch_phrase().split()[-1] for _ in range(10)]
    # Build a list of randomized ints from 1 to max_range
    # Precomputing this list avoids the need to generate a new random int in the loop below,
    # which at a scale >10000 clusters leads to duplicate values
    store_ids = random.sample([i for i in range(1, max_store_id_range)], k=max_store_id_range - 1)
    zone_ids = random.sample([i for i in range(1, max_zone_id_range)], k=max_zone_id_range - 1)

    for _ in range(0, cluster_count):
        organization_name = organization_name.replace(" ", "-").strip().lower()
        # Randomly select a country given it's weight. A higher weight value will be selected more often
        country = random.choices(
            population=list(country_codes.keys()), weights=[i["weight"] for i in country_codes.values()]
        )[0]
        gcp_region = country_codes[country]["gcp_region"]
        environment = random.choice(environments)
        store_id = store_ids.pop()  # Pop a value from the end of the _ids list precomputed above
        zone_id = zone_ids.pop()
        cluster_name = f"{country}{store_id}{environment[0]}"
        cluster_group = f"{country}-{environment}"
        cluster_tag = random.choice(cluster_tags)
        fleet_project_id = f"{organization_name}-global-{environment}-fleet"

        cluster_intent_data = {
            "store_id": f"{country}-{store_id}",  # de-13467
            "zone_name": f"{gcp_region}-edge-{fake.airport_iata().lower()}{zone_id}",  # europe-west3-edge-hnl28806
            "machine_project_id": f"{organization_name}-{country}-{environment}",
            "fleet_project_id": fleet_project_id,
            "cluster_name": cluster_name,
            "location": gcp_region,
            "node_count": 3,
            "cluster_ipv4_cidr": "10.0.0.0/17",
            "services_ipv4_cidr": "10.10.0.0/23",
            "external_load_balancer_ipv4_address_pools": country_codes[country]["lb_ips"],
            "sync_repo": f"https://github.com/{organization_name}/gdc-sync-repo/",
            "sync_branch": "main",
            "sync_dir": f"/hydrated/{country}/{cluster_name}",
            "secrets_project_id": fleet_project_id,
            "git_token_secrets_manager_name": f"{cluster_name}-gdc-pat",
            "cluster_version": "1.11.0",
            "maintenance_window_start": "2025-01-01T00:00:00Z",
            "maintenance_window_end": "2025-01-01T08:00:00Z",
            "maintenance_window_recurrence": "FREQ=WEEKLY;BYDAY=MO,TU,WE,TH",
            "subnet_vlans": "500,2000,2100",
            "recreate_on_delete": "false",
        }
        generated_csv_data["cluster_intent"].append(cluster_intent_data)

        cluster_registry_data = {
            "cluster_name": cluster_name,
            "cluster_group": cluster_group,
            "cluster_tags": cluster_tag,
            "platform_repository_revision": random.choice(
                [
                    "v1.0.0",
                    "v1.1.0",
                    "v1.1.1",
                    "v1.2.0",
                ]
            ),
            "workload_repository_revision": random.choice(
                [
                    "v2.0.0",
                    "v2.1.0",
                    "v2.1.1",
                    "v2.2.0",
                ]
            ),
        }
        generated_csv_data["cluster_registry"].append(cluster_registry_data)

        platform_data = {"cluster_name": cluster_name, "cluster_group": cluster_group, "cluster_tags": cluster_tag}
        generated_csv_data["platform"].append(platform_data)

        workload_data = {
            "cluster_name": cluster_name,
            "cluster_group": cluster_group,
            "project_id": fleet_project_id,
            "cluster_tags": cluster_tag,
            "country_code": country,
            "store_id": store_id,
            "gateway_ip": fake.ipv4_private(),
            "bos_vm_ip": f"{fake.ipv4_private()}/24",
            "vm1_ip": f"{fake.ipv4_private()}/24",
            "legacy_vm_ip": f"{fake.ipv4_private()}/24",
            "gsc01_vm_ip": "",
            "gsc02_vm_ip": "",
            "cluster_viewer_groups": "",
            "vm_support_groups": "",
            "vm_migrate_groups": "",
        }
        generated_csv_data["workload"].append(workload_data)

    for data_type, generated_data in generated_csv_data.items():
        write_csv_file(csv_data=generated_data, output_file=f"{data_type}_{output_file_suffix}")


def write_csv_file(csv_data, output_file: str):
    with open(output_file, "w", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=csv_data[0].keys())
        writer.writeheader()
        writer.writerows(csv_data)


def validate_user_options(**kwargs):
    """Validates user-provided command-line options.

    Args:
        **kwargs: A dictionary of keyword arguments representing the user options to be validated.
        Expected keys include 'cluster_count', 'output_file', and 'overwrite'.

    Raises:
        click.BadParameter: If the 'cluster_count' exceeds the maximum allowed value.
        click.ClickException: If an 'output_file' already exists and the 'overwrite' flag is not set.
    """
    cluster_count = kwargs.get("cluster_count", None)
    overwrite = kwargs.get("overwrite", None)
    output_file = kwargs.get("output_file", None)

    if cluster_count and cluster_count > max_cluster_count:
        raise click.BadParameter(
            f"Must be less-than or equal to {max_cluster_count} clusters.", param_hint="--cluster-count"
        )

    if output_file and os.path.isfile(output_file) and not overwrite:
        raise click.ClickException(f"{output_file} is already present and --overwrite was not provided.")


if __name__ == "__main__":
    generate_eps_data()
