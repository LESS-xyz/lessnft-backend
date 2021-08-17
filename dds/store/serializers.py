from rest_framework import serializers

from dds.settings import ALLOWED_HOSTS, SORT_STATUSES
from dds.consts import DECIMALS
from dds.rates.api import calculate_amount
from dds.store.models import (
    Status,
    Token,
    Collection,
    Ownership,
    Bid,
)
from dds.accounts.serializers import CreatorSerializer, UserSerializer
from dds.activity.serializers import TokenHistorySerializer 
from dds.accounts.models import MasterUser
from dds.rates.models import UsdRate

try:
    service_fee = MasterUser.objects.get().commission
except:
    print('master user not found, please add him for correct backend start')


class CurrencySerializer(serializers.ModelSerializer):
    class Meta:
        model = UsdRate
        fields = (
            "rate",
            "symbol",
            "name",
            "image",
        )


class TokenPatchSerializer(serializers.ModelSerializer):
    '''
    Serialiser for AdvUser model patching
    '''
    class Meta:
        model = Token
        fields = ('price', 'selling', 'minimal_bid')

    def update(self, instance, validated_data):
        print('started patch')
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


class OwnershipSerializer(serializers.ModelSerializer):
    id = serializers.SerializerMethodField()
    name = serializers.SerializerMethodField()
    avatar = serializers.CharField(read_only=True, source='owner.avatar')
    currency = CurrencySerializer()

    class Meta:
        model = Ownership
        read_only_fields = ("avatar",)
        fields = read_only_fields + (
            "id",
            "name",
            "quantity",
            "currency_price",
            "price",
            "currency",
        )

    def get_id(self, obj):
        return obj.owner.id

    def get_name(self, obj):
        return obj.owner.get_name()


class BetSerializer(serializers.ModelSerializer):
    user = CreatorSerializer()

    class Meta:
        model = Bid
        fields = (
            "id",
            "amount",
            "quantity",
            "user",
        )


class BidSerializer(serializers.ModelSerializer):
    bidder_avatar = serializers.CharField(read_only=True, source='user.avatar')
    bidder = serializers.SerializerMethodField()
    bidder_id = serializers.SerializerMethodField()
    amount = serializers.SerializerMethodField()
    currency = serializers.SerializerMethodField()

    class Meta:
        model = Bid
        fields = (
            "id",
            "bidder",
            "bidder_id",
            "bidder_avatar",
            "quantity",
            "amount",
            "currency",
        )

    def get_bidder(self, obj):
        return obj.user.get_name()

    def get_bidder_id(self, obj):
        return obj.user.id

    def get_amount(self, obj):
        return obj.amount / obj.token.currency.get_decimals

    def get_currency(self, obj):
        return CurrencySerializer(obj.token.currency).data


class CollectionSearchSerializer(serializers.ModelSerializer):
    id = serializers.SerializerMethodField()
    tokens = serializers.SerializerMethodField()

    class Meta:
        model = Collection
        read_only_fields = ("avatar",)
        fields = read_only_fields + (
            "id",
            "name",
            "tokens",
        )

    def get_id(self, obj):
        return obj.url


    def get_tokens(self, obj):
        tokens = obj.token_set.order_by(SORT_STATUSES["recent"])[:6]
        return [token.media for token in tokens]


class CollectionSlimSerializer(serializers.ModelSerializer):
    id = serializers.SerializerMethodField()

    class Meta:
        model = Collection
        read_only_fields = ("avatar",)
        fields = read_only_fields + (
            "id",
            "name",
            "address",
        )

    def get_id(self, obj):
        return obj.url


class TokenSlimSerializer(serializers.ModelSerializer):
    class Meta:
        model = Token
        fields = ("id", "media")


class TokenSerializer(serializers.ModelSerializer):
    available = serializers.SerializerMethodField()
    USD_price = serializers.SerializerMethodField()
    owners = serializers.SerializerMethodField()
    royalty = serializers.SerializerMethodField()
    creator = CreatorSerializer()
    collection = CollectionSlimSerializer()
    currency = CurrencySerializer()

    class Meta:
        model = Token
        read_only_fields = (
            "is_selling",
            "is_auc_selling",
        )
        fields = read_only_fields + (
            "id",
            "name",
            "media",
            "total_supply",
            "available",
            "price",
            "currency",
            "USD_price",
            "owners",
            "standart",
            "creator",
            "collection",
            "description",
            "details",
            "royalty",
            "selling",
            "updated_at",
        )
        
    def get_royalty(self, obj):
        return obj.creator_royalty

    def get_USD_price(self, obj):
        if obj.price:
            return calculate_amount(obj.price, obj.currency.symbol)[0]

    def get_available(self, obj):
        if obj.standart == "ERC721":
            available = 1 if obj.selling else 0
        else:
            owners = obj.ownership_set.filter(selling=True)
            available = 0
            for owner in owners:
                available += owner.quantity
        return available

    def get_owners(self, obj):
        if obj.standart == "ERC721":
            return UserSerializer(obj.owner).data
        owners = Ownership.objects.filter(token=obj, selling=True)
        return OwnershipSerializer(owners, many=True).data


class HotCollectionSerializer(CollectionSlimSerializer):
    tokens = serializers.SerializerMethodField()
    creator = CreatorSerializer()

    class Meta(CollectionSlimSerializer.Meta):
        fields = CollectionSlimSerializer.Meta.fields + (
            "symbol",
            "description",
            "standart",
            "short_url",
            "creator",
            "status",
            "deploy_hash",
            "deploy_block",
            "tokens",
        )

    def get_tokens(self, obj):
        tokens = obj.token_set.exclude(status=Status.BURNED).order_by(
            SORT_STATUSES["recent"]
        )[:6]
        return [token.media for token in tokens]


class UserCollectionSerializer(CollectionSlimSerializer):
    tokens = serializers.SerializerMethodField()
    creator = CreatorSerializer()

    class Meta(CollectionSlimSerializer.Meta):
        fields = CollectionSlimSerializer.Meta.fields + (
            "symbol",
            "description",
            "standart",
            "short_url",
            "creator",
            "status",
            "deploy_hash",
            "deploy_block",
            "tokens",
        )

    def get_tokens(self, obj):
        tokens = obj.token_set.all()[:6]   
        return [token.media for token in tokens]

    def get_creator(self, obj):
        return obj.creator.username


class CollectionSerializer(CollectionSlimSerializer):
    tokens = serializers.SerializerMethodField()
    creator = CreatorSerializer()

    class Meta(CollectionSlimSerializer.Meta):
        read_only_fields = CollectionSlimSerializer.Meta.read_only_fields + ("cover",)
        fields = CollectionSlimSerializer.Meta.fields + (
            "cover",
            "creator",
            "description",
            "tokens",
        )

    def get_tokens(self, obj):
        tokens = self.context.get("tokens") 
        return TokenSerializer(tokens, many=True).data


class TokenFullSerializer(TokenSerializer):
    bids = serializers.SerializerMethodField()
    selling = serializers.SerializerMethodField()
    minimal_bid = serializers.SerializerMethodField()
    highest_bid = serializers.SerializerMethodField()
    history = serializers.SerializerMethodField()
    tags = serializers.SerializerMethodField()
    sellers = serializers.SerializerMethodField()
    like_count = serializers.SerializerMethodField()
    service_fee = serializers.SerializerMethodField()
    owner_auction = serializers.SerializerMethodField()

    class Meta(TokenSerializer.Meta):
        fields = TokenSerializer.Meta.fields + (
            "bids",
            "highest_bid",
            "minimal_bid",
            "tags",
            "history",
            "sellers",
            "like_count",
            "service_fee",
            "internal_id",
            "owner_auction",
        )

    def get_selling(self, obj):
        if obj.standart == "ERC721":
            return obj.selling
        return obj.ownership_set.filter(selling=True).exists() 

    def get_minimal_bid(self, obj):
        if obj.minimal_bid:
            return obj.minimal_bid / obj.currency.get_decimals

    def get_highest_bid(self, obj):
        bids = obj.bid_set.filter(state=Status.COMMITTED).order_by(
            "-amount"
        ) 
        if bids:
            return bids.first().amount

    def get_bids(self, obj):
        return BidSerializer(obj.bid_set.all(), many=True).data

    def get_history(self, obj):
        history = obj.tokenhistory_set.exclude(method="Burn").order_by("-id")
        return TokenHistorySerializer(history, many=True).data

    def get_tags(self, obj):
        return [tag.name for tag in obj.tags.all()]

    def get_sellers(self, obj):
        sellers = obj.ownership_set.filter(price__isnull=False, selling=True).order_by(
            "currency_price"
        )
        return OwnershipSerializer(sellers, many=True).data

    def get_like_count(self, obj):
        return obj.useraction_set.count()

    def get_service_fee(self, obj):
        return service_fee

    def get_owner_auction(self, obj):
        return obj.get_owner_auction()
