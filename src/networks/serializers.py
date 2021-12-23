from rest_framework import serializers

from src.networks.models import Network
from src.rates.serializers import CurrencySerializer


class NetworkSerializer(serializers.ModelSerializer):
    currencies = serializers.SerializerMethodField()

    class Meta:
        model = Network
        fields = (
            "ipfs_icon",
            "name",
            "native_symbol",
            "currencies",
        )
        lookup_field = "name"

    def get_currencies(self, obj):
        return CurrencySerializer(obj.usdrate_set.all(), many=True).data

