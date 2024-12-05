from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from parameter_store.sot_csv_integration import SotCsvIntegration
from auto_api.util import cluster_intent_to_csv


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
