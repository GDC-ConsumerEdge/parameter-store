import io
import csv
from typing import Optional
from .models import ClusterIntent


def map_cluster_intent_names(name):
    if name == 'cluster':
        return 'cluster_name'
    elif name == 'zone_id':
        return 'store_id'
    else:
        return name


def cluster_intents_to_csv_data() -> Optional[bytes]:
    """
    Converts ClusterIntent data to CSV format bytes.
    """
    output = io.StringIO()
    writer = csv.writer(output, quoting=csv.QUOTE_NONNUMERIC)
    field_names = [field.name for field in ClusterIntent._meta.fields]
    writer.writerow(map(map_cluster_intent_names, field_names))

    intents = ClusterIntent.objects.all()
    for intent in intents:
        row = [str(getattr(intent, field)) for field in field_names]
        writer.writerow(row)

    return output.getvalue().encode('utf-8')  # Encode the string to bytes

