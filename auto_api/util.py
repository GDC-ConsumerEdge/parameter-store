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
import csv
import io
from typing import Optional

from parameter_store.models import ClusterIntent


def cluster_intent_to_csv() -> Optional[bytes]:
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


def map_cluster_intent_names(name):
    if name == 'cluster':
        return 'cluster_name'
    elif name == 'zone_id':
        return 'store_id'
    else:
        return name
