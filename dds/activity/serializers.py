from rest_framework import serializers

from dds.consts import DECIMALS
from dds.activity.models import TokenHistory, UserStat
from dds.accounts.serializers import UserSlimSerializer


class TokenHistorySerializer(serializers.ModelSerializer):
    id = serializers.SerializerMethodField()
    name = serializers.SerializerMethodField()
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


class UserStatSerializer(serializers.ModelSerializer):
    user = serializers.UserSlimSerializer()
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
