from rest_framework import serializers

from dds.networks import models


class NetworkSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Network
        fields = (
            "id",
            "name",
            "native_symbol",
            "endpoint",
            "needs_middleware",
            "fabric721_address",
            "fabric1155_address",
            "exchange_address",
        )
        lookup_field = "name"
