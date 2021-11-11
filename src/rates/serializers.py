from rest_framework import serializers
from src.rates.models import UsdRate


class UsdRateSerializer(serializers.ModelSerializer):
    class Meta:
        model = UsdRate
        fields = (
            "rate",
            "symbol",
            "image",
        )


class CurrencySerializer(serializers.ModelSerializer):
    class Meta:
        model = UsdRate
        fields = (
            "rate",
            "symbol",
            "name",
            "image",
        )