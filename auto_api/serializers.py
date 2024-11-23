from rest_framework import serializers
from .models import ExampleModel  # Replace with your model


class ExampleModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExampleModel
        fields = '__all__'  # Or specify the fields you want