from rest_framework import serializers

from dds.activity.models import TokenHistory, UserStat, BidsHistory
from dds.accounts.serializers import UserSlimSerializer
from dds.rates.api import get_decimals


class TokenHistorySerializer(serializers.ModelSerializer):
    id = serializers.SerializerMethodField()
    name = serializers.SerializerMethodField()
    avatar = serializers.SerializerMethodField()
    amount = serializers.SerializerMethodField()
    currency = serializers.CharField(source='token.currency')

    class Meta:
        model = TokenHistory
        fields = (
            'id',
            'name',
            'avatar',
            'method',
            'date',
            'price',
            'currency',
        )

    def get_id(self, obj):
        return obj.new_owner.id

    def get_name(self, obj):
        return obj.new_owner.get_name()

    def get_avatar(self, obj):
        return obj.new_owner.avatar

    def get_amount(self, obj):
        return int(obj.price / get_decimals(obj.token.currency))


class UserStatSerializer(serializers.ModelSerializer):
    user = UserSlimSerializer()
    price = serializers.SerializerMethodField()

    class Meta:
        model = UserStat
        fields = (
            'id',
            'user',
            'price',
        )

    def get_price(self, obj):
        status = self.context.get("status")
        time_range = self.context.get("time_range")
        stat_status = getattr(obj, status)
        return getattr(stat_status, time_range)


class BidsHistorySerializer(serializers.ModelSerializer):
    amount = serializers.SerializerMethodField()
    currency = serializers.CharField(source='token.currency')

    class Meta:
        model = BidsHistory
        fields = (
            'id',
            'price',
            'date',
            'currency',
        )

    def get_amount(self, obj):
        return int(obj.price / get_decimals(obj.token.currency))
