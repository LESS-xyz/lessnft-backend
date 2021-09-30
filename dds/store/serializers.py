from rest_framework import serializers

from dds.settings import SORT_STATUSES
from dds.consts import DECIMALS
from dds.rates.api import calculate_amount
from dds.store.models import (
    Status,
    Token,
    Collection,
    Ownership,
    Bid,
)
from dds.accounts.serializers import CreatorSerializer, UserSerializer, UserOwnerSerializer
from dds.activity.serializers import TokenHistorySerializer 
from dds.accounts.models import MasterUser
from dds.activity.models import UserAction
from dds.rates.models import UsdRate
from dds.rates.serializers import CurrencySerializer
from django.db.models import Min
import dds.settings_local
from dds.networks.serializers import NetworkSerializer

try:
    service_fee = MasterUser.objects.get().commission
except:
    print('master user not found, please add him for correct backend start')


class TokenPatchSerializer(serializers.ModelSerializer):
    '''
    Serialiser for AdvUser model patching
    '''
    class Meta:
        model = Token
        fields = (
            'currency_price', 
            'selling', 
            'currency_minimal_bid',
            'start_auction',
            'end_auction',
        )

    def update(self, instance, validated_data):
        print('started patch')
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


class OwnershipSerializer(serializers.ModelSerializer):
    id = serializers.SerializerMethodField()
    name = serializers.SerializerMethodField()
    price = serializers.SerializerMethodField()
    quantity = serializers.SerializerMethodField()
    avatar = serializers.CharField(read_only=True, source='owner.avatar')
    currency = serializers.SerializerMethodField()

    class Meta:
        model = Ownership
        read_only_fields = ("avatar",)
        fields = read_only_fields + (
            "id",
            "name",
            "quantity",
            "price",
            "currency",
        )

    def get_id(self, obj):
        return obj.owner.url

    def get_currency(self, obj):
        return CurrencySerializer(obj.token.currency).data

    def get_price(self, obj):
        return obj.currency_price

    def get_name(self, obj):
        return obj.owner.get_name()

    def get_quantity(self, obj):
        tracker = obj.transactiontracker_set.first()
        if obj.quantity and tracker and tracker.amount:
            return obj.quantity + obj.transactiontracker_set.first().amount
        return obj.quantity 


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
    is_liked = serializers.SerializerMethodField()
    price = serializers.SerializerMethodField()
    bids = serializers.SerializerMethodField()
    digital_key = serializers.SerializerMethodField()
    highest_bid = serializers.SerializerMethodField()
    highest_bid_USD = serializers.SerializerMethodField()
    creator = CreatorSerializer()
    collection = CollectionSlimSerializer()
    currency = CurrencySerializer()
    minimal_bid = serializers.SerializerMethodField()
    like_count = serializers.SerializerMethodField()
    network = serializers.SerializerMethodField()

    class Meta:
        model = Token
        read_only_fields = (
            "is_selling",
            "is_auc_selling",
            "is_timed_auc_selling",
            "like_count",
        )
        fields = read_only_fields + (
            "id",
            "name",
            "media",
            "animation",
            "total_supply",
            "available",
            "price",
            "currency",
            "USD_price",
            "owners",
            "standart",
            "creator",
            "collection",
            "minimal_bid",
            "description",
            "details",
            "royalty",
            "is_liked",
            "selling",
            "updated_at",
            "start_auction",
            "end_auction",
            "format",
            "digital_key",
            "bids",
            "highest_bid",
            "highest_bid_USD",
            "network",
        )
        
    def get_royalty(self, obj):
        return obj.creator_royalty
        
    def get_network(self, obj):
        network = obj.currency.network
        return NetworkSerializer(network).data

    def get_like_count(self, obj):
        return obj.useraction_set.count()

    def get_highest_bid(self, obj):
        bids = obj.bid_set.filter(state=Status.COMMITTED).order_by(
            "-amount"
        ) 
        if bids:
            return BidSerializer(bids.first()).data

    def get_minimal_bid(self, obj):
        return obj.currency_minimal_bid

    def get_highest_bid_USD(self, obj):
        if self.get_highest_bid(obj) and obj.currency:
            amount = float(self.get_highest_bid(obj).get('amount'))
            decimals = obj.currency.get_decimals
            return calculate_amount(amount*decimals, obj.currency.symbol)[0]

    def get_bids(self, obj):
        return BidSerializer(obj.bid_set.filter(state=Status.COMMITTED), many=True).data

    def get_USD_price(self, obj):
        if obj.price:
            return calculate_amount(obj.price, obj.currency.symbol)[0]

    def get_price(self, obj):
        if obj.standart == "ERC721":
            return obj.currency_price
        currency = obj.ownership_set.filter(
            selling=True,
            currency_price__isnull=False,
        ).aggregate(Min("currency_price"))
        return currency.get("currency_price__min")

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
            return UserOwnerSerializer(obj.owner, context={
                "price": obj.currency_price,
                "currency": CurrencySerializer(obj.currency).data,
            }).data
        owners = obj.ownership_set.all()
        return OwnershipSerializer(owners, many=True).data

    def get_is_liked(self, obj):
        user = self.context.get("user") 
        if user and not user.is_anonymous:
            return UserAction.objects.filter(method="like", token=obj, user=user).exists()
        return False

    def get_digital_key(self, obj):
        user = self.context.get("user") 
        if obj.standart=="ERC721" and user==obj.owner:
            return obj.digital_key
        if obj.standart=="ERC1155" and user in obj.owners.all():
            return obj.digital_key
        return None


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
        tokens = Token.token_objects.committed().filter(collection=obj).order_by(
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
    selling = serializers.SerializerMethodField()
    history = serializers.SerializerMethodField()
    tags = serializers.SerializerMethodField()
    sellers = serializers.SerializerMethodField()
    service_fee = serializers.SerializerMethodField()
    owner_auction = serializers.SerializerMethodField()
    is_liked = serializers.SerializerMethodField()

    class Meta(TokenSerializer.Meta):
        fields = TokenSerializer.Meta.fields + (
            "tags",
            "history",
            "sellers",
            "is_liked",
            "service_fee",
            "internal_id",
            "owner_auction",
        )

    def get_selling(self, obj):
        if obj.standart == "ERC721":
            return obj.selling
        return obj.ownership_set.filter(selling=True).exists() 

    def get_history(self, obj):
        history = obj.tokenhistory_set.exclude(method="Burn").order_by("-id")
        return TokenHistorySerializer(history, many=True).data

    def get_tags(self, obj):
        return [tag.name for tag in obj.tags.all()]

    def get_sellers(self, obj):
        sellers = obj.ownership_set.filter(currency_price__isnull=False, selling=True).order_by(
            "currency_price"
        )
        return OwnershipSerializer(sellers, many=True).data

    def get_service_fee(self, obj):
        return obj.currency.service_fee

    def get_owner_auction(self, obj):
        return obj.get_owner_auction()

    def get_is_liked(self, obj):
        user = self.context.get("user") 
        if user and not user.is_anonymous:
            return UserAction.objects.filter(method="like", token=obj, user=user).exists()
        return False


class CollectionMetadataSerializer(serializers.ModelSerializer):

    image = serializers.SerializerMethodField()
    seller_fee_basis_points = serializers.SerializerMethodField()
    fee_recipient = serializers.SerializerMethodField()

    class Meta:
        model = Collection
        read_only_fields = (
            "image",
            "seller_fee_basis_points",
            "fee_recipient",
        )
        fields = read_only_fields + (
            "name",
            "description",
        )

    def get_image(self, obj):
        image = obj.avatar
        return image

    def get_seller_fee_basis_points(self, obj):
        if obj.name == dds.settings_local.COLLECTION_721 or obj.name == dds.settings_local.COLLECTION_1155:
            return 0
        else:
            return 1000

    def get_fee_recipient(self, obj):
        fee_recipient = obj.creator.username
        return fee_recipient

