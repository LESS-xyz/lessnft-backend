from rest_framework import serializers

from dds.consts import DECIMALS
from dds.activity.models import TokenHistory


class TokenHistorySerializer(serializers.ModelSerializer):
    id = serializers.SerializerMethodField()
    name = serializers.SerializerMethodField()
    price = serializers.SerializerMethodField()

    class Meta:
        modle = TokenHistory
        fields = (
            'id',
            'name',
            'avatar',
            'method',
            'date',
            'price',
        )

    def get_id(self, obj):
        return obj.new_owner.id

    def get_name(self, obj):
        return obj.new_owner.get_name()

    def get_price(self, obj):
        if obj.price:
            return obj.price / DECIMALS[obj.token.currency]
        return None
