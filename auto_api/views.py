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
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .sot_csv_integration import SotCsvIntegration
from .util import cluster_intent_to_csv


class UpdateSot(APIView):
    # This view class is disabled in URLs
    # Consider re-implementing views as JSON APIs
    def get(self, request):
        try:
            sot = SotCsvIntegration()
            sot.get_git_token_from_secrets_manager()
            content = cluster_intent_to_csv()
            if content:
                sot.update_source_of_truth(content)
                return Response({"message": "SoT updated successfully"}, status=status.HTTP_200_OK)
            else:
                raise Exception('Failed to read SoT from database.')
        except Exception as e:
            print(type(e))
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
