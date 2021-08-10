from rest_framework import serializers

from dds.networks import models


class NetworkSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Network
        fields = (
            'id',
            'name',
            'erc721_main_address', 
            'erc1155_main_address', 
            'erc721_fabric_address', 
            'erc1155_fabric_address', 
            'exchange_address', 
            'endpoint',
            'needs_middleware',
        )
        lookup_field = 'name'