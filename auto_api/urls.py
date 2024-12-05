from django.urls import path, include
from rest_framework.routers import DefaultRouter

router = DefaultRouter()

urlpatterns = [
    # path('update_sot/', UpdateSot.as_view(), name='update-sot'),  # Existing APIView
    path('', include(router.urls)),  # Include the router's URLs
]
