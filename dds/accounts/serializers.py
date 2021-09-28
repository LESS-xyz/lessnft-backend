from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied
from rest_auth.registration.serializers import SocialLoginSerializer

from dds.accounts.utils import valid_metamask_message
from dds.settings import ALLOWED_HOSTS
from dds.store.models import Token
from dds.accounts.models import AdvUser
from dds.rates.serializers import CurrencySerializer


class TokenSlimSerializer(serializers.ModelSerializer):
    class Meta:
        model = Token
        fields = ("id", "media")


class PatchSerializer(serializers.ModelSerializer):
    '''
    Serialiser for AdvUser model patching
    '''
    class Meta:
        model = AdvUser
        fields = ('display_name', 'custom_url', 'bio', 'twitter', 'instagram', 'site')

    def update(self, instance, validated_data):
        print('started patch')
        for attr, value in validated_data.items():
            if attr !='bio':
                my_filter = {attr: value}
                if attr == 'display_name' and value == '':
                    pass
                elif AdvUser.objects.filter(**my_filter).exclude(id=instance.id):
                    return {attr: f'this {attr} is occupied'}
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
        session = self.context["request"].session
        #message = session.get("metamask_message")
        #if message is None:

        message = attrs["msg"]

        print(
            "metamask login, address",
            address,
            "message",
            message,
            "signature",
            signature,
            flush=True,
        )
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
        #read_only_fields = ("avatar", "cover",)
        read_only_fields = ("avatar", "cover_ipfs",)
        fields = ("id", "owner",) + read_only_fields

    def get_id(self, obj):
        return obj.url

    def get_owner(self, obj):
        return obj.get_name()


class BaseAdvUserSerializer(serializers.ModelSerializer):
    id = serializers.SerializerMethodField()
    name = serializers.SerializerMethodField()

    class Meta:
        model = AdvUser
        read_only_fields = ("avatar",)
        fields = read_only_fields + ("id", "name",)

    def get_id(self, obj):
        return obj.url

    def get_name(self, obj):
        return obj.get_name()

 
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
        fields = BaseAdvUserSerializer.Meta.fields + ("his_followers", )

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
            "bio",
            "twitter",
            "instagram",
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
        fields = UserSerializer.Meta.fields + ("likes", )

    def get_likes(self, obj):
        return obj.followers.filter(method="like").count()
