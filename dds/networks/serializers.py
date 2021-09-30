from rest_framework import serializers

from dds.networks import models


class NetworkSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Network
        fields = (
            "name",
            "native_symbol",
        )
        lookup_field = "name"
