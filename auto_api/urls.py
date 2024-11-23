from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import UpdateSot, ExampleModelViewSet  # Import your ViewSet
from rest_framework.routers import DefaultRouter
from .views import ExampleModelViewSet

router = DefaultRouter()
router.register(r'examplemodels', ExampleModelViewSet)  # Customize the URL path

urlpatterns = [
    path('update_sot/', UpdateSot.as_view(), name='update-sot'),  # Existing APIView
    path('', include(router.urls)),  # Include the router's URLs
]