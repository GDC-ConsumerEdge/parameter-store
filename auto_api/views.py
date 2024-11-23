from django.shortcuts import render

# Create your views here.
from rest_framework import viewsets
from .serializers import ExampleModelSerializer
from .models import ExampleModel


class ExampleModelViewSet(viewsets.ModelViewSet):
    queryset = ExampleModel.objects.all()
    serializer_class = ExampleModelSerializer


from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from parameter_store.sot_csv_integration import SotCsvIntegration
from parameter_store.utils import cluster_intents_to_csv_data


class UpdateSot(APIView):
    def get(self, request):
        try:
            sot = SotCsvIntegration()
            sot.get_git_token_from_secrets_manager()
            content = cluster_intents_to_csv_data()
            if content:
                print(content)
                sot.update_source_of_truth(content)
                # print(sot.retrieve_source_of_truth())
                return Response({"message": "SoT updated successfully"}, status=status.HTTP_200_OK)
            else:
                raise Exception('Failed to read SoT from database.')
        except Exception as e:
            print(type(e))
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)