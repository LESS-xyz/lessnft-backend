import logging
from collections import Counter
from decimal import Decimal

from src.accounts.serializers import CreatorSerializer, UserOwnerSerializer
from src.activity.models import UserAction
from src.activity.serializers import TokenHistorySerializer
from src.networks.serializers import NetworkSerializer
from src.rates.api import calculate_amount
from src.rates.serializers import CurrencySerializer
from src.settings import config
from src.store.models import (
    Bid, 
    Collection, 
    Ownership, 
    Status, 
    Token,
    TransactionTracker,
    ViewsTracker,
)
from django.db.models import Count, Min, Sum
from rest_framework import serializers


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
        logging.info('started patch')
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
        tracker_amount = TransactionTracker.objects.filter(ownership=obj).aggregate(owner_amount=Sum('amount'))
        if obj.quantity and tracker_amount:
            tracker_amount = tracker_amount.get('owner_amount', 0)
            tracker_amount = tracker_amount or 0
            return obj.quantity - tracker_amount
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
            "state",
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
            "state",
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
        tokens = obj.token_set.order_by(config.SORT_STATUSES.recent)[:6]
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
    tags = serializers.SerializerMethodField()
    owners = serializers.SerializerMethodField()
    royalty = serializers.SerializerMethodField()
    is_liked = serializers.SerializerMethodField()
    price = serializers.SerializerMethodField()
    bids = serializers.SerializerMethodField()
    digital_key = serializers.SerializerMethodField()
    highest_bid = serializers.SerializerMethodField()
    highest_bid_USD = serializers.SerializerMethodField()
    minimal_bid_USD = serializers.SerializerMethodField()
    sellers = serializers.SerializerMethodField()
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
            "tags",
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
            "minimal_bid_USD",
            "network",
            "sellers",
        )
        
    def get_royalty(self, obj):
        return obj.creator_royalty

    def get_tags(self, obj):
        return [{"value": tag.name, "media": tag.ipfs_icon} for tag in obj.tags.all()]

    def get_network(self, obj):
        network = obj.currency.network
        return NetworkSerializer(network).data

    def get_like_count(self, obj):
        return obj.useraction_set.count()

    def get_sellers(self, obj):
        sellers = obj.ownership_set.filter(currency_price__isnull=False, selling=True).order_by(
            "currency_price"
        )
        return OwnershipSerializer(sellers, many=True).data

    def get_minimal_bid_USD(self, obj):
        if self.get_minimal_bid(obj) and obj.currency:
            amount = float(self.get_minimal_bid(obj))
            decimals = obj.currency.get_decimals
            return calculate_amount(amount*decimals, obj.currency.symbol)[0]

    def get_highest_bid(self, obj):
        bids = obj.bid_set.filter(state=Status.COMMITTED).order_by(
            "-amount"
        ) 
        if bids:
            return BidSerializer(bids.first()).data

    def get_minimal_bid(self, obj):
        if obj.standart == "ERC721":
            return obj.currency_minimal_bid
        minimal_bids = obj.ownership_set.filter(
            selling=True, 
            currency_minimal_bid__isnull=False,
        ).values_list('currency_minimal_bid', flat=True)
        return min(minimal_bids) if minimal_bids else None

    def get_highest_bid_USD(self, obj):
        if self.get_highest_bid(obj) and obj.currency:
            amount = float(self.get_highest_bid(obj).get('amount'))
            decimals = obj.currency.get_decimals
            return calculate_amount(amount*decimals, obj.currency.symbol)[0]

    def get_bids(self, obj):
        return BidSerializer(obj.bid_set.filter(state=Status.COMMITTED), many=True).data

    def get_USD_price(self, obj):
        price = self.get_price(obj)
        decimals = obj.currency.get_decimals
        if price:
            return calculate_amount(price*decimals, obj.currency.symbol)[0]
        if not self.get_highest_bid_USD(obj) and self.get_minimal_bid(obj):
            return calculate_amount(self.get_minimal_bid(obj) * decimals, obj.currency.symbol)[0]

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
            owners_amount = obj.ownership_set.filter(selling=True).aggregate(total_amount=Sum('quantity'))
            track_owners = obj.transactiontracker_set.filter(ownership__selling=True).aggregate(total_amount=Sum('amount'))
            track_owners = track_owners['total_amount'] or 0
            owners_amount = owners_amount['total_amount'] or 0
            available = owners_amount - track_owners
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
    likes_count = serializers.SerializerMethodField()
    class Meta(CollectionSlimSerializer.Meta):
        fields = CollectionSlimSerializer.Meta.fields + (
            "symbol",
            "description",
            "standart",
            "short_url",
            "creator",
            "status",
            "deploy_block",
            "tokens",
            "likes_count",
        )

    def get_tokens(self, obj):
        tokens = Token.objects.committed().filter(collection=obj).order_by(
            config.SORT_STATUSES.recent
        )[:6]
        return [token.media for token in tokens]

    def get_likes_count(self, obj):
        return obj.token_set.all().aggregate(likes_count=Count('useraction'))

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
            "is_default",
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
    attributes = serializers.SerializerMethodField()
    tokens_count = serializers.SerializerMethodField()

    class Meta(CollectionSlimSerializer.Meta):
        read_only_fields = CollectionSlimSerializer.Meta.read_only_fields + ("cover",)
        fields = CollectionSlimSerializer.Meta.fields + (
            "cover",
            "creator",
            "description",
            "tokens",
            "tokens_count",
            "attributes",
        )

    def get_tokens_count(self, obj):
        return self.context.get("tokens_count")

    def get_tokens(self, obj):
        tokens = self.context.get("tokens") 
        return TokenSerializer(tokens, many=True).data

    def get_attributes(self, obj):
        token_details = Token.objects.committed().filter(collection=obj).values_list('details', flat=True)

        attribute_count = []
        #Getting a list of all keys(token attributes) from the list of token details:
        all_attributes = set().union(*(d.keys() for d in token_details if d is not None))
        #initialising a counter to iterate over value dicts in a list:
        for attribute in all_attributes:
            #Counting all occurrencies of each attribute value and writing it into a list of dicts like
            #{'title': Attribute, properties: [{ 'name': value1, 'count': occurencies of value1}, 
            # 'name': value2, 'count': occurencies of value2}], ...}]}]
            value_amount = Counter(token[attribute] for token in token_details if attribute in token)
            element = {"title": attribute, "properties": []}
            for value, amount in value_amount.items():
                element["properties"].append({"name": value, "count": amount})
            attribute_count.append(element)

        return attribute_count


class TokenFullSerializer(TokenSerializer):
    selling = serializers.SerializerMethodField()
    history = serializers.SerializerMethodField()
    service_fee = serializers.SerializerMethodField()
    currency_service_fee = serializers.SerializerMethodField()
    USD_service_fee = serializers.SerializerMethodField()
    owner_auction = serializers.SerializerMethodField()
    is_liked = serializers.SerializerMethodField()
    views = serializers.SerializerMethodField()

    class Meta(TokenSerializer.Meta):
        fields = TokenSerializer.Meta.fields + (
            "history",
            "is_liked",
            "service_fee",
            "currency_service_fee",
            "USD_service_fee",
            "internal_id",
            "owner_auction",
            "views",
        )

    def get_selling(self, obj):
        if obj.standart == "ERC721":
            return obj.selling
        return obj.ownership_set.filter(selling=True).exists() 

    def get_history(self, obj):
        history = obj.tokenhistory_set.exclude(method__in=["Mint", "Burn"]).order_by("-id")
        return TokenHistorySerializer(history, many=True).data

    def get_service_fee(self, obj):
        return obj.currency.service_fee

    def get_currency_service_fee(self, obj):
        price = self.get_price(obj)
        if price:
            return price / 100 * Decimal(obj.currency.service_fee)
        bids = obj.bid_set.filter(state=Status.COMMITTED).order_by(
            "-amount"
        )
        if bids:
            return bids.first().amount / 100 * Decimal(obj.currency.service_fee)
        if self.get_minimal_bid(obj):
            return self.get_minimal_bid(obj) / 100 * Decimal(obj.currency.service_fee)

    def get_USD_service_fee(self, obj):
        price = self.get_price(obj)
        if price:
            decimals = obj.currency.get_decimals
            value = price / 100 * Decimal(obj.currency.service_fee) * decimals
            return calculate_amount(value, obj.currency.symbol)[0]
        amount = self.get_minimal_bid(obj)
        if self.get_highest_bid(obj) and obj.currency:
            amount = Decimal(self.get_highest_bid(obj).get('amount'))
        if amount:
            decimals = obj.currency.get_decimals
            value = amount / 100 * decimals
            return calculate_amount(value, obj.currency.symbol)[0]

    def get_owner_auction(self, obj):
        return obj.get_owner_auction()

    def get_is_liked(self, obj):
        user = self.context.get("user") 
        if user and not user.is_anonymous:
            return UserAction.objects.filter(method="like", token=obj, user=user).exists()
        return False

    def get_views(self, obj):
        return ViewsTracker.objects.filter(token=obj).count()


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
        if obj.is_default:
            return 0
        return 1000

    def get_fee_recipient(self, obj):
        fee_recipient = obj.creator.username
        return fee_recipient

