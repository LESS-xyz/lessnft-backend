import logging

from django.db.models import Q
from rest_auth.registration.serializers import SocialLoginSerializer
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied

from src.accounts.models import AdvUser
from src.accounts.utils import valid_metamask_message
from src.store.models import Status, Token


class TokenSlimSerializer(serializers.ModelSerializer):
    class Meta:
        model = Token
        fields = ("id", "media")


class PatchSerializer(serializers.ModelSerializer):
    """
    Serialiser for AdvUser model patching
    """

    class Meta:
        model = AdvUser
        fields = (
            "display_name",
            "custom_url",
            "bio",
            "twitter",
            "instagram",
            "facebook",
            "site",
        )

    def update(self, instance, validated_data):
        logging.info("started patch")
        for attr, value in validated_data.items():
            if attr != "bio" and value:
                my_filter = {attr: value}
                if attr == "display_name" and value == "":
                    pass
                elif AdvUser.objects.filter(**my_filter).exclude(id=instance.id):
                    return {attr: f"this {attr} is occupied"}
            setattr(instance, attr, value)
        instance.save()
        return instance


class MetamaskLoginSerializer(SocialLoginSerializer):
    address = serializers.CharField(required=False, allow_blank=True)
    msg = serializers.CharField(required=False, allow_blank=True)
    signed_msg = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        address = attrs["address"]
        signature = attrs["signed_msg"]
        message = attrs["msg"]

        if valid_metamask_message(address, message, signature):
            metamask_user = AdvUser.objects.filter(username__iexact=address).first()

            if metamask_user is None:
                self.user = AdvUser.objects.create_user(username=address)
            else:
                self.user = metamask_user

            attrs["user"] = self.user

            if not self.user.is_active:
                raise PermissionDenied(1035)

        else:
            raise PermissionDenied(1034)

        return attrs


class CoverSerializer(serializers.ModelSerializer):
    id = serializers.SerializerMethodField()
    owner = serializers.SerializerMethodField()

    class Meta:
        model = AdvUser
        # read_only_fields = ("avatar", "cover",)
        read_only_fields = (
            "avatar",
            "cover_ipfs",
        )
        fields = (
            "id",
            "owner",
        ) + read_only_fields

    def get_id(self, obj):
        return obj.url

    def get_owner(self, obj):
        return obj.get_name()


class BaseAdvUserSerializer(serializers.ModelSerializer):
    id = serializers.SerializerMethodField()
    name = serializers.SerializerMethodField()
    created_tokens = serializers.SerializerMethodField()
    owned_tokens = serializers.SerializerMethodField()
    address = serializers.SerializerMethodField()

    class Meta:
        model = AdvUser
        read_only_fields = (
            "avatar",
            "created_at",
            "twitter",
            "instagram",
            "facebook",
            "site",
            "created_tokens",
            "owned_tokens",
            "address",
            "display_name",
            "custom_url",
            "bio",
            "is_verificated",
        )
        fields = read_only_fields + (
            "id",
            "name",
        )

    def get_id(self, obj):
        return obj.url

    def get_address(self, obj):
        return obj.username

    def get_name(self, obj):
        return obj.get_name()

    def get_created_tokens(self, obj):
        return obj.token_creator.filter(status=Status.COMMITTED).count()

    def get_owned_tokens(self, obj):
        owned_tokens = Token.objects.filter(
            Q(owner=obj) | Q(owners=obj),
        ).filter(status=Status.COMMITTED)
        network = self.context.get("network")
        if network:
            owned_tokens = owned_tokens.filter(
                collection__network__name__icontains=network
            )
        return owned_tokens.count()


class UserOwnerSerializer(BaseAdvUserSerializer):
    quantity = serializers.SerializerMethodField()
    price = serializers.SerializerMethodField()
    currency = serializers.SerializerMethodField()

    class Meta(BaseAdvUserSerializer.Meta):
        fields = BaseAdvUserSerializer.Meta.fields + (
            "quantity",
            "price",
            "currency",
        )

    def get_quantity(self, obj):
        return 1

    def get_price(self, obj):
        return self.context.get("price")

    def get_currency(self, obj):
        return self.context.get("currency")


class FollowingSerializer(BaseAdvUserSerializer):
    followers_count = serializers.SerializerMethodField()
    tokens = serializers.SerializerMethodField()

    class Meta(BaseAdvUserSerializer.Meta):
        fields = BaseAdvUserSerializer.Meta.fields + ("followers_count", "tokens")

    def get_followers_count(self, obj):
        return obj.following.filter(method="follow").count()

    def get_tokens(self, obj):
        tokens = obj.token_owner.all()[:5]
        return TokenSlimSerializer(tokens, many=True).data


class UserSearchSerializer(BaseAdvUserSerializer):
    followers = serializers.SerializerMethodField()
    tokens = serializers.SerializerMethodField()

    class Meta(BaseAdvUserSerializer.Meta):
        fields = BaseAdvUserSerializer.Meta.fields + ("followers", "tokens")

    def get_followers(self, obj):
        return obj.following.count()

    def get_tokens(self, obj):
        tokens = obj.token_owner.all()[:6]
        return TokenSlimSerializer(tokens, many=True).data


class FollowerSerializer(BaseAdvUserSerializer):
    his_followers = serializers.SerializerMethodField()

    class Meta(BaseAdvUserSerializer.Meta):
        fields = BaseAdvUserSerializer.Meta.fields + ("his_followers",)

    def get_his_followers(self, obj):
        return obj.following.filter(method="follow").count()


class CreatorSerializer(BaseAdvUserSerializer):
    address = serializers.SerializerMethodField()

    class Meta(BaseAdvUserSerializer.Meta):
        fields = BaseAdvUserSerializer.Meta.fields + ("address", "is_verificated")

    def get_address(self, obj):
        return obj.username


class UserSlimSerializer(serializers.ModelSerializer):
    id = serializers.SerializerMethodField()
    address = serializers.SerializerMethodField()

    class Meta:
        model = AdvUser
        read_only_fields = ("avatar",)
        fields = read_only_fields + (
            "id",
            "address",
            "display_name",
            "custom_url",
            "created_at",
            "bio",
            "twitter",
            "instagram",
            "facebook",
            "site",
            "is_verificated",
        )

    def get_id(self, obj):
        return obj.url

    def get_address(self, obj):
        return obj.username


class UserSerializer(UserSlimSerializer):
    follows = serializers.SerializerMethodField()
    follows_count = serializers.SerializerMethodField()
    followers = serializers.SerializerMethodField()
    followers_count = serializers.SerializerMethodField()

    class Meta(UserSlimSerializer.Meta):
        read_only_fields = UserSlimSerializer.Meta.read_only_fields + ("cover",)
        fields = UserSlimSerializer.Meta.fields + (
            "cover",
            "follows",
            "follows_count",
            "followers",
            "followers_count",
        )

    def get_follows(self, obj):
        followers = obj.followers.filter(method="follow")
        users = [follower.whom_follow for follower in followers]
        return FollowerSerializer(users, many=True).data

    def get_follows_count(self, obj):
        return obj.followers.filter(method="follow").count()

    def get_followers(self, obj):
        following = obj.following.filter(method="follow")
        users = [follower.user for follower in following]
        return FollowerSerializer(users, many=True).data

    def get_followers_count(self, obj):
        return obj.following.filter(method="follow").count()


class SelfUserSerializer(UserSerializer):
    likes = serializers.SerializerMethodField()

    class Meta(UserSerializer.Meta):
        fields = UserSerializer.Meta.fields + ("likes",)

    def get_likes(self, obj):
        return obj.followers.filter(method="like").count()
