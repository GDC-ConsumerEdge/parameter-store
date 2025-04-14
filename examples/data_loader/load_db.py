###############################################################################
# Copyright 2024 Google, LLC
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
#
###############################################################################
import argparse
import collections
import csv
import os

import django
from django.db import models, transaction


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--wipe', action='store_true')
    parser.add_argument('--cluster-intent-csv', default='cluster_intent.csv')
    parser.add_argument('--platform-csv', default='platform.csv')
    parser.add_argument('--workload-csv', default='workload.csv')
    return parser.parse_args()


def main(*, wipe, cluster_intent_csv, platform_csv, workload_csv):
    setup_django()

    if wipe:
        delete_all_objects()

    intent = load_intent(cluster_intent_csv)

    merged = collections.defaultdict(dict)

    for file_name in [platform_csv, workload_csv]:
        read_csv(file_name, merged)

    load_db(intent, merged)

    create_validators()

    print('Done')


def get_or_create(cache: dict, model: models.Model, id_: str, id_field: str = 'name'):
    if not id_ in cache:
        # print(f'Creating {model} {id_field} = {id_}')
        cache[id_] = model.objects.get_or_create(**{id_field: id_})[0]
    return cache[id_]


def load_db(intent, merged):
    from parameter_store import models

    with transaction.atomic():
        print('Processing cluster groups')
        unique_groups = set((i['cluster_group']) for _, i in merged.items() if i['cluster_group'])
        group_objs = models.Group.objects.bulk_create((models.Group(name=i) for i in unique_groups))
        groups_cache = {obj.name: obj for obj in group_objs}

        print('Processing cluster tags')
        unique_tags = set((i['cluster_tags']) for _, i in merged.items() if i['cluster_tags'])
        tag_objs = models.Tag.objects.bulk_create((models.Tag(name=i) for i in unique_tags))
        tags_cache = {obj.name: obj for obj in tag_objs}

        clus_data_field_cache = {}
        clusters = []
        cluster_tags = []
        intents = []
        cluster_datas = []

        for name, row in merged.items():
            print(f'Processing objects for {row['cluster_name']}...')

            cluster = models.Cluster(name=row['cluster_name'],
                                     group=groups_cache[row['cluster_group']])

            clusters.append(cluster)

            processed_fields = {'cluster_name', 'cluster_group', 'cluster_tags'}

            for tag in row['cluster_tags'].split(','):
                if tag:
                    cluster_tags.append(models.ClusterTag(cluster=cluster, tag=tags_cache[tag]))
            processed_fields.add('cluster_tags')

            try:
                intents.append(models.ClusterIntent(cluster=cluster, **intent[cluster.name]))
            except KeyError:
                pass

            remaining_fields = set(row.keys()) - processed_fields

            for field in remaining_fields:
                cluster_data_field = get_or_create(
                    clus_data_field_cache, models.CustomDataField, field
                )

                value = row[field].strip()
                cluster_datas.append(models.ClusterData(cluster=cluster, field=cluster_data_field,
                                                        value=value))

        print('Bulk inserting data...')
        models.Cluster.objects.bulk_create(clusters)
        models.ClusterTag.objects.bulk_create(cluster_tags)
        models.ClusterIntent.objects.bulk_create(intents)
        models.ClusterData.objects.bulk_create(cluster_datas)

def create_validators():
    print('Creating validators...')
    from parameter_store import models

    # @formatter:off
    models.Validator.objects.bulk_create(
        [
            models.Validator(
                name=validator['name'],
                validator=validator['validator'],
                parameters=validator['parameters'],
            ) for validator in [
                {
                    'name': 'Valid CIDR IPv4 Address',
                    'validator': 'parameter_store.validation.IPv4AddressWithCIDR',
                    'parameters': {},
                },
                {
                    'name': 'Valid IPv4 or IPv6 Address',
                    'validator': 'parameter_store.validation.IPAddressValidator',
                    'parameters': {},
                },
                {
                    'name': 'Valid Email Address',
                    'validator': 'parameter_store.validation.EmailAddressValidator',
                    'parameters': {},
                },
                {
                    'name': "Valid Example Cluster Name Length",
                    'validator': 'parameter_store.validation.StringLengthValidator',
                    'parameters': {"max_value": 12, "min_value": 12},
                },
                {
                    'name': "Valid Example Cluster Name Format",
                    'validator': 'parameter_store.validation.StringRegexValidator',
                    'parameters': {"regex": "^[a-z]{2}\\d{5}cls\\d{2}$"},
                },
                {
                    'name': 'Comma-separated list of emails',
                    'validator': 'parameter_store.validation.CommaSeparatedEmailsValidator',
                    'parameters': {"message": "expected a comma-separated list of email addresses"},
                },
                {
                    'name': "Valid Example Country Code",
                    'validator': 'parameter_store.validation.StringRegexValidator',
                    'parameters': {"regex": "^[a-z]{2}$"},
                },
                {
                    'name': "Valid Example Store ID",
                    'validator': 'parameter_store.validation.StringRegexValidator',
                    'parameters': {"regex": "^[A-Za-z]{2}\\d{5}$"},
                },
            ]
        ]
    )
    # @formatter:on

    print('Assigning validators to custom data fields...')
    models.ValidatorAssignment.objects.bulk_create(
        [
            models.ValidatorAssignment(
                validator=models.Validator.objects.get(
                    name="Valid Example Cluster Name Length"),
                model='parameter_store.models.Cluster',
                model_field='Cluster.name',
            ),
            models.ValidatorAssignment(
                validator=models.Validator.objects.get(
                    name="Valid Example Cluster Name Format"),
                model='parameter_store.models.Cluster',
                model_field='Cluster.name',
            )
        ]
    )

    # @formatter:off
    models.CustomDataFieldValidatorAssignment.objects.bulk_create(
        [
            models.CustomDataFieldValidatorAssignment(
                field=models.CustomDataField.objects.get(name=assignment['field']),
                validator=models.Validator.objects.get(name=assignment['validator'])
            ) for assignment in [
                {
                    'field': 'example_ip',
                    'validator': 'Valid CIDR IPv4 Address'
                },
            ]
        ]
    )
    # @formatter:on


def read_csv(file_name: str, data: collections.defaultdict[dict]):
    with open(file_name, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            data[row['cluster_name']].update(row)


def delete_all_objects():
    from parameter_store import models

    for model in [
        models.ValidatorAssignment,
        models.CustomDataFieldValidatorAssignment,
        models.Validator,
        models.CustomDataField,
        models.ClusterData,
        models.GroupData,
        models.ClusterIntent,
        models.ClusterFleetLabel,
        models.ClusterTag,
        models.Tag,
        models.Cluster,
        models.Group
    ]:
        print('Deleting rows in', model.__name__, '...')
        model.objects.all().delete()

    print('Done deleting objects')
    print()


def setup_django():
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'parameter_store.settings')
    django.setup()


def load_intent(cluster_intent_csv) -> dict[str, dict[str, str]]:
    intent = {}
    with open(cluster_intent_csv) as f:
        reader = csv.DictReader(f)
        for row in reader:
            # fix intent to match models
            name = row['cluster_name']
            del row['cluster_name']

            row['unique_zone_id'] = row['store_id']
            del row['store_id']

            for value in ('maintenance_window_start', 'maintenance_window_end'):
                if row[value] == "":
                    row[value] = None

            if row['recreate_on_delete'].lower() == 'false':
                row['recreate_on_delete'] = False
            elif row['recreate_on_delete'].lower() == 'true':
                row['recreate_on_delete'] = True

            intent[name] = row
    return intent


if __name__ == '__main__':
    args = parse_args()
    main(**vars(args))
