import json

from src.accounts.serializers import BaseAdvUserSerializer, UserSlimSerializer
from src.activity.models import BidsHistory, TokenHistory, UserStat
from src.rates.api import get_decimals
from rest_framework import serializers


class TokenHistorySerializer(serializers.ModelSerializer):
    id = serializers.SerializerMethodField()
    name = serializers.SerializerMethodField()
    avatar = serializers.SerializerMethodField()
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


class UserStatSerializer(serializers.ModelSerializer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['user'] = BaseAdvUserSerializer(context=self.context)
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
        if isinstance(stat_status, str):
            stat_status = json.loads(stat_status)
            return stat_status[time_range]


class BidsHistorySerializer(serializers.ModelSerializer):
    user = UserSlimSerializer()
    amount = serializers.SerializerMethodField()
    currency = serializers.CharField(source='token.currency')

    class Meta:
        model = BidsHistory
        fields = (
            'id',
            'price',
            'user',
            'date',
            'currency',
        )

    def get_amount(self, obj):
        return int(obj.price / get_decimals(obj.token.currency))
