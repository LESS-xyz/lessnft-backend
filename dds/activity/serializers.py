from rest_framework import serializers

from dds.consts import DECIMALS
from dds.activity.models import TokenHistory


class TokenHistorySerializer(serializers.ModelSerializer):
    id = serializers.SerializerMethodField()
    name = serializers.SerializerMethodField()
    price = serializers.SerializerMethodField()
    avatar = serializers.SerializerMethodField()

    class Meta:
        model = TokenHistory
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

    def get_avatar(self, obj):
        return obj.new_owner.avatar

    def get_price(self, obj):
        if obj.price:
            return obj.price / obj.token.currency.get_decimals
        return None
