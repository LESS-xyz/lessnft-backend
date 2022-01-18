import json

from rest_framework import serializers

from src.accounts.serializers import BaseAdvUserSerializer, UserSlimSerializer
from src.activity.models import BidsHistory, TokenHistory, UserStat
from src.rates.api import get_decimals
from src.rates.serializers import CurrencySerializer


class TokenHistorySerializer(serializers.ModelSerializer):
    new_owner = UserSlimSerializer()
    old_owner = UserSlimSerializer()
    currency = CurrencySerializer()

    class Meta:
        model = TokenHistory
        fields = (
            "id",
            "date",
            "method",
            "new_owner",
            "old_owner",
            "price",
            "USD_price",
            "amount",
            "currency",
        )


class UserStatSerializer(serializers.ModelSerializer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["user"] = BaseAdvUserSerializer(context=self.context)

    price = serializers.SerializerMethodField()

    class Meta:
        model = UserStat
        fields = (
            "id",
            "user",
            "price",
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
    currency = serializers.CharField(source="token.currency")

    class Meta:
        model = BidsHistory
        fields = (
            "id",
            "price",
            "user",
            "date",
            "currency",
        )

    def get_amount(self, obj):
        return int(obj.price / get_decimals(obj.token.currency))


class ActivitySerializer(serializers.Serializer):
    token_id = serializers.SerializerMethodField()
    token_image = serializers.SerializerMethodField()
    token_name = serializers.SerializerMethodField()
    currency = serializers.SerializerMethodField()
    amount = serializers.SerializerMethodField()
    price = serializers.SerializerMethodField()
    from_id = serializers.SerializerMethodField()
    from_image = serializers.SerializerMethodField()
    from_address = serializers.SerializerMethodField()
    from_name = serializers.SerializerMethodField()
    to_id = serializers.SerializerMethodField()
    to_image = serializers.SerializerMethodField()
    to_address = serializers.SerializerMethodField()
    to_name = serializers.SerializerMethodField()
    method = serializers.CharField()
    date = serializers.DateTimeField()
    id = serializers.IntegerField()
    is_viewed = serializers.BooleanField()

    def _get_user_from(self, obj):
        try:
            user_from = getattr(obj, "user")
        except AttributeError:
            user_from = getattr(obj, "old_owner")
        return user_from

    def _get_user_to(self, obj):
        try:
            user_to = getattr(obj, "whom_follow")
        except AttributeError:
            try:
                user_to = getattr(obj, "new_owner")
            except AttributeError:
                user_to = None
        return user_to

    def get_token_id(self, obj):
        if obj.token:
            return obj.token.id
        return None

    def get_token_image(self, obj):
        if obj.token:
            return obj.token.image
        return None

    def get_token_name(self, obj):
        if obj.token:
            return obj.token.name
        return None

    def get_currency(self, obj):
        if hasattr(obj, "currency"):
            currency = obj.currency.symbol if obj.currency else None
            return currency

    def get_amount(self, obj):
        try:
            amount = getattr(obj, "amount")
        except AttributeError:
            amount = None
        return amount

    def get_price(self, obj):
        try:
            price = getattr(obj, "price")
        except AttributeError:
            price = ""
        return price

    def get_from_id(self, obj):
        user_from = self._get_user_from(obj)
        if user_from:
            return user_from.custom_url if user_from.custom_url else user_from.id
        return None

    def get_from_image(self, obj):
        user_from = self._get_user_from(obj)
        if user_from:
            return user_from.avatar
        return None

    def get_from_address(self, obj):
        user_from = self._get_user_from(obj)
        if user_from:
            return user_from.username
        return None

    def get_from_name(self, obj):
        user_from = self._get_user_from(obj)
        if user_from:
            return user_from.get_name()
        return None

    def get_to_id(self, obj):
        user_to = self._get_user_to(obj)
        if user_to:
            return user_to.custom_url if user_to.custom_url else user_to.id
        return None

    def get_to_image(self, obj):
        user_to = self._get_user_to(obj)
        if user_to:
            return user_to.avatar
        return None

    def get_to_address(self, obj):
        user_to = self._get_user_to(obj)
        if user_to:
            return user_to.username
        return None

    def get_to_name(self, obj):
        user_to = self._get_user_to(obj)
        if user_to:
            return user_to.get_name()
        return None
