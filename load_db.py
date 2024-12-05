import argparse
import collections
import csv
import os

import django


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--wipe', action='store_true')
    parser.add_argument('--cluster-intent-csv', default='cluster_intent.csv')
    parser.add_argument('--cluster-registry-csv', default='cluster_registry.csv')
    parser.add_argument('--platform-csv', default='platform.csv')
    parser.add_argument('--workload-csv', default='workload.csv')
    return parser.parse_args()


def main(*, wipe, cluster_intent_csv, cluster_registry_csv, platform_csv, workload_csv):
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


def load_db(intent, merged):
    from parameter_store import models

    for name, row in merged.items():
        print(f'Creating objects for {row['cluster_name']}...')

        processed_fields = set()

        group, _ = models.Group.objects.get_or_create(name=row['cluster_group'])
        processed_fields.add('cluster_group')

        cluster = models.Cluster(name=row['cluster_name'], group=group)
        cluster.save()
        processed_fields.add('cluster_name')

        tags = row['cluster_tags'].split(',')
        for tag in tags:
            tag, _ = models.Tag.objects.get_or_create(name=tag)
            cluster_tag = models.ClusterTag(cluster=cluster, tag=tag)
            cluster_tag.save()
        processed_fields.add('cluster_tags')

        try:
            cluster_intent = models.ClusterIntent(cluster=cluster, **intent[cluster.name])
        except KeyError:
            continue
        cluster_intent.save()

        remaining_fields = set(row.keys()) - processed_fields

        for field in remaining_fields:
            cluster_data_field, _ = models.ClusterDataField.objects.get_or_create(name=field)

            value = row[field].strip()
            cluster_data = models.ClusterData(
                cluster=cluster, field=cluster_data_field, value=value
            )
            cluster_data.save()


def create_validators():
    print('Creating validators...')
    from parameter_store import models

    for validator in [
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
            'name': "Valid McDonald's Cluster Name Length",
            'validator': 'parameter_store.validation.StringLengthValidator',
            'parameters': {"max_value": 12, "min_value": 12},
        },
        {
            'name': "Valid McDonald's Cluster Name Format",
            'validator': 'parameter_store.validation.StringRegexValidator',
            'parameters': {"regex": "^[a-z]{2}\\d{5}cls\\d{2}$"},
        },
        {
            'name': 'Comma-separated list of emails',
            'validator': 'parameter_store.validation.CommaSeparatedEmailsValidator',
            'parameters': {"message": "expected a comma-separated list of email addresses"},
        },
        {
            'name': "Valid McDonald's Country Code",
            'validator': 'parameter_store.validation.StringRegexValidator',
            'parameters': {"regex": "^[a-z]{2}$"},
        },
        {
            'name': "Valid McDonald's Store ID",
            'validator': 'parameter_store.validation.StringRegexValidator',
            'parameters': {"regex": "^[A-Za-z]{2}\\d{5}$"},
        },
        {
            'name': 'Value is exactly "foo"',
            'validator': 'parameter_store.validation.ExactValueValidator',
            'parameters': {"value": "foo"},
        },
        {
            'name': 'One of "foo", "bar", "baz", "quux"',
            'validator': 'parameter_store.validation.IPAddressValidator',
            'parameters': {"choices": ["foo", "bar", "baz", "quux"]},
        },
    ]:
        models.Validator(
            name=validator['name'],
            validator=validator['validator'],
            parameters=validator['parameters'],
        ).save()

    print('Assigning validators to custom data fields...')

    models.ValidatorAssignment(
        validator=models.Validator.objects.get(name="Valid McDonald's Cluster Name Length"),
        model='parameter_store.models.Cluster',
        model_field='name',
    ).save()

    models.ValidatorAssignment(
        validator=models.Validator.objects.get(name="Valid McDonald's Cluster Name Format"),
        model='parameter_store.models.Cluster',
        model_field='name',
    ).save()

    for assignment in [
        {
            'field': 'bos_vm_ip',
            'validator': 'Valid CIDR IPv4 Address'
        },
        {
            'field': 'qsrsoft_vm_ip',
            'validator': 'Valid CIDR IPv4 Address'
        },
        {
            'field': 'gsc01_vm_ip',
            'validator': 'Valid CIDR IPv4 Address'
        },
        {
            'field': 'gsc02_vm_ip',
            'validator': 'Valid CIDR IPv4 Address'
        },
        {
            'field': 'gateway_ip',
            'validator': 'Valid IPv4 or IPv6 Address'
        },
        {
            'field': 'store_id',
            'validator': "Valid McDonald's Store ID"
        },
        {
            'field': 'country_code',
            'validator': "Valid McDonald's Country Code"
        },
        {
            'field': 'vm_migrate_groups',
            'validator': 'Comma-separated list of emails'
        },
        {
            'field': 'vm_support_groups',
            'validator': 'Comma-separated list of emails'
        },
        {
            'field': 'cluster_viewer_groups',
            'validator': 'Comma-separated list of emails'
        },
    ]:
        models.ClusterDataFieldValidatorAssignment(
            field=models.ClusterDataField.objects.get(name=assignment['field']),
            validator=models.Validator.objects.get(name=assignment['validator'])
        ).save()


def read_csv(file_name: str, data: dict):
    with open(file_name, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            data[row['cluster_name']].update(row)


def delete_all_objects():
    from parameter_store import models

    for model in [
        models.ValidatorAssignment,
        models.ClusterDataFieldValidatorAssignment,
        models.Validator,
        models.ClusterDataField,
        models.ClusterData,
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

            row['location'] = row['store_id']
            del row['store_id']

            for value in ('maintenance_window_start', 'maintenance_window_end'):
                if row[value] == "":
                    row[value] = None

            if row['recreate_on_delete'] == 'false':
                row['recreate_on_delete'] = False
            elif row['recreate_on_delete'] == 'true':
                row['recreate_on_delete'] = True

            row['git_token_secret_manager_name'] = row['git_token_secrets_manager_name']
            del row['git_token_secrets_manager_name']

            intent[name] = row
    return intent


if __name__ == '__main__':
    args = parse_args()
    main(**vars(args))
