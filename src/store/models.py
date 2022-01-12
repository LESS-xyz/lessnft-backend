import json
import logging
import random
import secrets
from datetime import datetime
from decimal import Decimal
from typing import Tuple, Union

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator
from django.db import models
from django.db.models import Exists, OuterRef, Q, Sum
from django.db.models.signals import post_save, pre_save
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response

from src.accounts.models import AdvUser, DefaultAvatar
from src.consts import (
    COLLECTION_CREATION_GAS_LIMIT,
    MAX_AMOUNT_LEN,
    TOKEN_BUY_GAS_LIMIT,
    TOKEN_MINT_GAS_LIMIT,
    TOKEN_TRANSFER_GAS_LIMIT,
)
from src.networks.models import Network
from src.rates.api import calculate_amount
from src.rates.models import UsdRate
from src.settings import config
from src.utilities import get_media_from_ipfs, sign_message, to_int

from .services.ipfs import get_ipfs_by_hash

OPENSEA_MEDIA_PATH = "https://lh3.googleusercontent.com/"


class Status(models.TextChoices):
    PENDING = "Pending"
    FAILED = "Failed"
    COMMITTED = "Committed"
    BURNED = "Burned"
    EXPIRED = "Expired"


class CollectionQuerySet(models.QuerySet):
    def committed(self):
        return self.filter(status=Status.COMMITTED)

    def get_by_short_url(self, short_url):
        collection_id = None
        if isinstance(short_url, int) or short_url.isdigit():
            collection_id = int(short_url)
        return self.get(Q(id=collection_id) | Q(short_url=short_url))

    def user_collections(self, user, network=None):
        if user:
            assert (
                user.is_authenticated
            ), "Getting collections for an unauthenticated user"
        if network is None or network == "undefined":
            return self.filter(status=Status.COMMITTED).filter(
                Q(is_default=True) | Q(creator=user)
            )
        return self.filter(
            status=Status.COMMITTED,
            network__name__icontains=network,
        ).filter(Q(is_default=True) | Q(creator=user))

    def hot_collections(self, network=None):
        if network is None or network == "undefined":
            return self.filter(is_default=False).filter(
                Exists(Token.objects.committed().filter(collection__id=OuterRef("id")))
            )
        return (
            self.filter(is_default=False)
            .filter(
                network__name__icontains=network,
            )
            .filter(
                Exists(Token.objects.committed().filter(collection__id=OuterRef("id"))),
            )
        )

    def network(self, network):
        if network is None or network == "undefined":
            return self
        return self.filter(network__name__icontains=network)

    def tag(self, tag):
        if not tag:
            return self
        return self.filter(
            Exists(
                Token.objects.committed().filter(
                    tags__name=tag,
                    collection__id=OuterRef("id"),
                )
            )
        )


class CollectionManager(models.Manager):
    def get_queryset(self):
        return CollectionQuerySet(self.model, using=self._db)

    def committed(self):
        return self.get_queryset().committed()

    def get_by_short_url(self, short_url):
        """Return collection by id or short_url"""
        return self.get_queryset().get_by_short_url(short_url)

    def user_collections(self, user, network=None):
        """Return collections for user (with default collections)"""
        return self.get_queryset().user_collections(user, network)

    def hot_collections(self, network=None):
        """Return non-default collections with committed tokens"""
        return self.get_queryset().hot_collections(network)

    def network(self, network):
        """Return collections filtered by network name"""
        return self.get_queryset().network(network)

    def tag(self, tag):
        """Return collections filtered by exists token with tag"""
        return self.get_queryset().tag(tag)


class Collection(models.Model):
    DISPLAY_THEMES = [
        ("Padded", "Padded"),
        ("Contained", "Contained"),
        ("Covered", "Covered"),
    ]
    name = models.CharField(max_length=50)
    avatar_ipfs = models.CharField(max_length=200, null=True, default=None)
    cover_ipfs = models.CharField(max_length=200, null=True, default=None, blank=True)
    address = models.CharField(max_length=60, null=True, blank=True)
    symbol = models.CharField(max_length=30)
    description = models.TextField(null=True, blank=True)
    standart = models.CharField(
        max_length=10,
        choices=[("ERC721", "ERC721"), ("ERC1155", "ERC1155")],
    )
    short_url = models.CharField(
        max_length=30,
        default=None,
        null=True,
        blank=True,
        unique=True,
    )
    creator = models.ForeignKey(
        "accounts.AdvUser",
        on_delete=models.PROTECT,
        null=True,
        default=None,
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    deploy_block = models.IntegerField(null=True, default=None)
    network = models.ForeignKey("networks.Network", on_delete=models.CASCADE)
    is_default = models.BooleanField(default=False)
    is_nsfw = models.BooleanField(default=False)
    display_theme = models.CharField(
        max_length=10, choices=DISPLAY_THEMES, default="Padded"
    )
    site = models.URLField(blank=True, null=True, default=None)
    discord = models.URLField(blank=True, null=True, default=None)
    twitter = models.URLField(blank=True, null=True, default=None)
    instagram = models.URLField(blank=True, null=True, default=None)
    medium = models.URLField(blank=True, null=True, default=None)
    telegram = models.URLField(blank=True, null=True, default=None)

    objects = CollectionManager()

    class Meta:
        unique_together = [["address", "network"]]

    @property
    def avatar(self):
        if self.avatar_ipfs and self.avatar_ipfs.startswith(OPENSEA_MEDIA_PATH):
            return self.avatar_ipfs
        return get_media_from_ipfs(self.avatar_ipfs)

    @property
    def cover(self):
        if self.cover_ipfs:
            if self.cover_ipfs.startswith(OPENSEA_MEDIA_PATH):
                return self.cover_ipfs
            return get_media_from_ipfs(self.cover_ipfs)

    @property
    def url(self):
        return self.short_url if self.short_url else self.id

    @property
    def ethereum_address(self):
        return self.network.get_ethereum_address(self.address)

    def __str__(self):
        return self.name

    def save_in_db(self, request, avatar):
        self.name = request.data.get("name")
        self.symbol = request.data.get("symbol")
        self.address = request.data.get("address")
        network_name = request.query_params.get("network")
        network = Network.objects.filter(name__icontains=network_name).first()
        self.network = network
        self.avatar_ipfs = avatar
        self.standart = request.data.get("standart")
        self.description = request.data.get("description")
        short_url = request.data.get("short_url")
        if short_url:
            self.short_url = short_url
        self.site = request.data.get("site")
        self.discord = request.data.get("discord")
        self.twitter = request.data.get("twitter")
        self.instagram = request.data.get("instagram")
        self.medium = request.data.get("medium")
        self.telegram = request.data.get("telegram")
        self.display_theme = request.data.get("display_theme", "Padded")
        self.is_nsfw = request.data.get("is_nsfw", "false").lower() == "true"
        self.creator = request.user
        self.save()

    def create_token(self, creator, ipfs, signature, amount):
        if self.standart == "ERC721":
            value = self.network.contract_call(
                method_type="read",
                contract_type="erc721fabric",
                function_name="getFee",
                input_params=(),
                input_type=(),
                output_types=("uint256",),
            )
            logging.info(f"fee: {value}")

            initial_tx = self.network.contract_call(
                method_type="write",
                contract_type="erc721main",
                address=self.address,
                gas_limit=TOKEN_MINT_GAS_LIMIT,
                nonce_username=creator.username,
                tx_value=value,
                function_name="mint",
                input_params=(ipfs, signature),
                input_type=("string", "bytes"),
            )
        else:

            value = self.network.contract_call(
                method_type="read",
                contract_type="erc1155fabric",
                function_name="getFee",
                input_params=(),
                input_type=(),
                output_types=("uint256",),
            )

            initial_tx = self.network.contract_call(
                method_type="write",
                contract_type="erc1155main",
                address=self.address,
                gas_limit=TOKEN_MINT_GAS_LIMIT,
                nonce_username=creator.username,
                tx_value=value,
                function_name="mint",
                input_params=(int(amount), ipfs, signature),
                input_type=("uint256", "string", "bytes"),
                send=False,
            )

        return initial_tx

    @classmethod
    def collection_is_unique(
        cls, name, symbol, short_url, network
    ) -> Tuple[bool, Union[Response, None]]:
        logging.info(f"{name}, {network}")
        network = Network.objects.get(name__icontains=network)
        if Collection.objects.filter(name=name).filter(network=network):
            return False, Response(
                {"name": "this collection name is occupied"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if Collection.objects.filter(symbol=symbol).filter(network=network):
            return False, Response(
                {"symbol": "this collection symbol is occupied"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if short_url and Collection.objects.filter(short_url=short_url):
            return False, Response(
                {"short_url": "this collection short_url is occupied"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return True, None

    @classmethod
    def create_contract(cls, name, symbol, standart, owner, network):
        baseURI = ""
        signature = sign_message(["address"], [config.SIGNER_ADDRESS])

        if standart == "ERC721":

            return network.contract_call(
                method_type="write",
                contract_type="erc721fabric",
                gas_limit=COLLECTION_CREATION_GAS_LIMIT,
                nonce_username=owner.username,
                tx_value=None,
                function_name="makeERC721",
                input_params=(name, symbol, baseURI, config.SIGNER_ADDRESS, signature),
                input_type=("string", "string", "string", "address", "bytes"),
                send=False,
            )

        return network.contract_call(
            method_type="write",
            contract_type="erc1155fabric",
            gas_limit=COLLECTION_CREATION_GAS_LIMIT,
            nonce_username=owner.username,
            tx_value=None,
            function_name="makeERC1155",
            input_params=(name, baseURI, config.SIGNER_ADDRESS, signature),
            send=False,
            input_type=("string", "string", "address", "bytes"),
        )

    def get_contract(self):
        if self.standart == "ERC721":
            return self.network.get_erc721main_contract(self.address)
        return self.network.get_erc1155main_contract(self.address)


def collection_created_dispatcher(sender, instance, created, **kwargs):
    if created and not instance.avatar_ipfs:
        default_avatars = DefaultAvatar.objects.all().values_list("image", flat=True)
        if default_avatars:
            instance.avatar_ipfs = random.choice(default_avatars)
            instance.save()


post_save.connect(collection_created_dispatcher, sender=Collection)


class NotableDrop(models.Model):
    image = models.CharField(max_length=200, null=True, default=None, blank=True)
    description = models.CharField(max_length=500, null=True, default=None, blank=True)
    collection = models.OneToOneField(
        "store.Collection",
        on_delete=models.CASCADE,
    )


def validate_nonzero(value):
    if value < 0:
        raise ValidationError(
            "Quantity %(value)s is not allowed",
            params={"value": value},
        )


class TokenQuerySet(models.QuerySet):
    def committed(self):
        return self.filter(status=Status.COMMITTED)

    def network(self, network):
        if network is None or network == "undefined":
            return self
        return self.filter(collection__network__name__icontains=network)


class TokenManager(models.Manager):
    def get_queryset(self):
        return TokenQuerySet(self.model, using=self._db)

    def committed(self):
        """Return tokens with status committed"""
        return self.get_queryset().committed()

    def network(self, network):
        """Return token filtered by collection network name"""
        return self.get_queryset().network(network)


class Token(models.Model):
    name = models.CharField(max_length=200)
    tx_hash = models.CharField(max_length=200, null=True, blank=True)
    ipfs = models.CharField(max_length=200, null=True, default=None)
    image = models.CharField(max_length=200, null=True, blank=True, default=None)
    animation_file = models.CharField(
        max_length=200,
        null=True,
        blank=True,
        default=None,
    )
    format = models.CharField(max_length=10, null=True, default="image")
    total_supply = models.PositiveIntegerField(validators=[validate_nonzero])
    currency_price = models.DecimalField(
        max_digits=MAX_AMOUNT_LEN,
        default=None,
        blank=True,
        null=True,
        decimal_places=18,
    )
    currency_minimal_bid = models.DecimalField(
        max_digits=MAX_AMOUNT_LEN,
        default=None,
        blank=True,
        null=True,
        decimal_places=18,
    )
    currency = models.ForeignKey(
        "rates.UsdRate",
        on_delete=models.PROTECT,
        null=True,
        default=None,
        blank=True,
    )
    owner = models.ForeignKey(
        "accounts.AdvUser",
        on_delete=models.PROTECT,
        related_name="%(class)s_owner",
        null=True,
        blank=True,
    )
    owners = models.ManyToManyField("accounts.AdvUser", through="Ownership", null=True)
    creator = models.ForeignKey(
        "accounts.AdvUser", on_delete=models.PROTECT, related_name="%(class)s_creator"
    )
    creator_royalty = models.PositiveIntegerField(validators=[MaxValueValidator(99)])
    collection = models.ForeignKey("Collection", on_delete=models.CASCADE)
    internal_id = models.PositiveIntegerField(null=True, blank=True)
    description = models.TextField(blank=True, null=True)
    _properties = models.JSONField(blank=True, null=True, default=None)
    _rankings = models.JSONField(blank=True, null=True, default=None)
    _stats = models.JSONField(blank=True, null=True, default=None)
    selling = models.BooleanField(default=False)
    status = models.CharField(
        max_length=50,
        choices=Status.choices,
        default=Status.PENDING,
    )
    updated_at = models.DateTimeField(auto_now_add=True)
    tags = models.ManyToManyField("Tags", blank=True, null=True)
    is_favorite = models.BooleanField(default=False)
    start_auction = models.DateTimeField(blank=True, null=True, default=None)
    end_auction = models.DateTimeField(blank=True, null=True, default=None)
    digital_key = models.CharField(max_length=1000, blank=True, null=True, default=None)
    external_link = models.CharField(max_length=200, null=True, blank=True)

    objects = TokenManager()

    def _details_getter(self, field):
        details = list()
        for key, item in getattr(self, field).items():
            item.update({"trait_type": key})
            details.append(item)
        return details

    @property
    def properties(self):
        return self._details_getter("_properties")

    @properties.setter
    def properties(self, value):
        if value:
            self._properties = {
                item.pop("trait_type"): {k: str(v) for k, v in item.items()}
                for item in value
            }

    @property
    def rankings(self):
        return self._details_getter("_rankings")

    @rankings.setter
    def rankings(self, value):
        if value:
            self._rankings = {
                rank.pop("trait_type"): {k: to_int(v) for k, v in rank.items()}
                for rank in value
            }

    @property
    def stats(self):
        return self._details_getter("_stats")

    @stats.setter
    def stats(self, value):
        if value:
            self._stats = {item.pop("trait_type"): item for item in value}

    @property
    def media(self):
        if not self.image:
            self.image = get_ipfs_by_hash(self.ipfs).get("image")
            self.save(update_fields=["image"])
        return self.image

    @property
    def animation(self):
        if not self.animation_file:
            try:
                self.animation_file = get_ipfs_by_hash(self.ipfs).get("animation_url")
                self.save(update_fields=["animation_file"])
            except Exception as e:
                print(e)
        return self.animation_file

    @property
    def price(self):
        if self.currency_price and self.currency:
            return int(self.currency_price * self.currency.get_decimals)

    @property
    def usd_price(self):
        if self.price:
            return calculate_amount(self.price, self.currency.symbol)[0]
        if self.minimal_bid:
            return calculate_amount(self.minimal_bid, self.currency.symbol)[0]

    @property
    def minimal_bid(self):
        if self.currency_minimal_bid and self.currency:
            return int(self.currency_minimal_bid * self.currency.get_decimals)

    @property
    def standart(self):
        return self.collection.standart

    @property
    def is_selling(self):
        if self.standart == "ERC1155":
            return self.ownership_set.filter(
                selling=True,
                currency_price__isnull=False,
            ).exists()
        return bool(self.selling and self.price and self.currency)

    @property
    def is_auc_selling(self):
        if self.standart == "ERC1155":
            return self.ownership_set.filter(
                selling=True,
                currency_price__isnull=True,
                currency_minimal_bid__isnull=False,
            ).exists()
        return bool(self.selling and self.minimal_bid and self.currency)

    @property
    def is_timed_auc_selling(self):
        if (
            self.standart == "ERC721"
            and self.start_auction is not None
            and self.end_auction is not None
        ):
            try:
                return bool(
                    self.selling
                    and not self.price
                    and self.start_auction < timezone.now()
                    and self.end_auction > timezone.now()
                )
            except Exception as e:
                logging.error(e)
        return False

    def __str__(self):
        return self.name

    def is_valid(self, user=None) -> Tuple[bool, Union[Response, None]]:
        if self.status == Status.BURNED:
            return False, Response(
                {"error": "burned"}, status=status.HTTP_404_NOT_FOUND
            )
        if self.internal_id is None:
            return False, Response(
                "token is not validated yet, please wait up to 5 minutes. If problem persists,"
                "please contact us through support form",
                status=status.HTTP_400_BAD_REQUEST,
            )
        if user:
            if self.standart == "ERC721":
                if self.owner != user:
                    return False, Response(
                        {"error": "this token doesn't belong to you"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
            else:
                if not self.ownership_set.filter(owner=user).exists():
                    return False, Response(
                        {"error": "this token doesn't belong to you"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
        return True, None

    def is_valid_for_buy(
        self, token_amount, seller_id
    ) -> Tuple[bool, Union[Response, None]]:
        is_valid, response = self.is_valid()
        if not is_valid:
            return False, response
        if self.standart == "ERC721":
            if not self.selling:
                return False, Response(
                    {"error": "token not selling"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        else:
            if not self.ownership_set.filter(selling=True).exists():
                return False, Response(
                    {"error": "token not selling"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        if self.standart == "ERC721" and token_amount != 0:
            return False, Response(
                {"error": "wrong token amount"}, status=status.HTTP_400_BAD_REQUEST
            )
        elif self.standart == "ERC1155" and token_amount == 0:
            return False, Response(
                {"error": "wrong token amount"}, status=status.HTTP_400_BAD_REQUEST
            )

        if self.standart == "ERC1155" and not seller_id:
            return False, Response(
                {"error": "The 'sellerId' field is required for token 1155."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if seller_id:
            try:
                seller = AdvUser.objects.get_by_custom_url(seller_id)
                ownership = self.ownership_set.filter(owner=seller).filter(selling=True)
                if not ownership:
                    return False, Response(
                        {"error": "user is not owner or token is not on sell"}
                    )
            except AdvUser.DoesNotExist:
                return False, Response(
                    {"error": "user not found"}, status=status.HTTP_404_NOT_FOUND
                )

        return True, None

    def _parse_and_save_details(self, details):
        details = json.loads(details)
        methods = [
            "properties",
            "stats",
            "rankings",
        ]
        for method in methods:
            data = [d for d in details if d.get("display_type") == method]
            if data:
                setattr(self, method, data)

    def save_in_db(self, request, ipfs):
        self.name = request.data.get("name")
        self.status = Status.PENDING
        self.ipfs = ipfs
        self.format = request.data.get("format")
        self.description = request.data.get("description")
        self.creator_royalty = request.data.get("creator_royalty")
        self.creator = request.user
        collection = request.data.get("collection")
        self.collection = Collection.objects.committed().get_by_short_url(collection)
        self.total_supply = request.data.get("total_supply")
        self.digital_key = request.data.get("digital_key")
        self.external_link = request.data.get("external_link")

        start_auction = request.data.get("start_auction")
        end_auction = request.data.get("end_auction")

        if start_auction:
            self.start_auction = datetime.fromtimestamp(int(start_auction))
        if end_auction:
            self.end_auction = datetime.fromtimestamp(int(end_auction))

        price = request.data.get("price")
        if price:
            price = Decimal(price)
        else:
            price = None
        minimal_bid = request.data.get("minimal_bid")
        if minimal_bid:
            minimal_bid = Decimal(minimal_bid)
        selling = request.data.get("selling", "false")
        selling = selling.lower() == "true"
        currency = request.data.get("currency")

        if currency:
            currency = (
                UsdRate.objects.filter(symbol__iexact=currency)
                .filter(network=self.collection.network)
                .first()
            )
        self.currency = currency

        if self.standart == "ERC721":
            self.total_supply = 1
            self.owner = self.creator
            self.selling = selling
            self.currency_price = price
            self.currency_minimal_bid = minimal_bid
        else:
            self.full_clean()
            self.save()
            self.owners.add(request.user)
            self.save()
            ownership = Ownership.objects.get(owner=self.creator, token=self)
            ownership.quantity = request.data.get("total_supply")
            ownership.selling = selling
            ownership.currency_price = price
            ownership.currency = currency
            ownership.currency_minimal_bid = minimal_bid
            ownership.full_clean()
            ownership.save()
        self.full_clean()

        self.save()

        details = request.data.get("details")
        if details:
            self._parse_and_save_details(details)

        tag, _ = Tags.objects.get_or_create(name="New")
        self.tags.add(tag)
        is_nsfw = request.data.get("is_nsfw", "false").lower() == "true"

        if is_nsfw or self.collection.is_nsfw:
            tag, _ = Tags.objects.get_or_create(name="NSFW")
            self.tags.add(tag)

        self.save()

    def get_highest_bid(self):
        bids = self.bid_set.committed().values_list("amount", flat=True)
        return max(bids) if bids else None

    def get_main_contract(self):
        if self.standart == "ERC721":
            return self.collection.network.get_erc721main_contract(
                self.collection.address
            )
        return self.collection.network.get_erc1155main_contract(self.collection.address)

    def transfer(self, old_owner, new_owner, amount=None):
        if self.standart == "ERC721":
            return self.collection.network.contract_call(
                method_type="write",
                contract_type="erc721main",
                address=self.collection.address,
                gas_limit=TOKEN_TRANSFER_GAS_LIMIT,
                nonce_username=old_owner.username,
                tx_value=None,
                function_name="transferFrom",
                input_params=(
                    self.collection.network.get_ethereum_address(old_owner.username),
                    self.collection.network.get_ethereum_address(new_owner),
                    self.internal_id,
                ),
                input_type=("string", "string", "uint256"),
                is1155=False,
            )
        return self.collection.network.contract_call(
            method_type="write",
            contract_type="erc1155main",
            address=self.collection.address,
            gas_limit=TOKEN_TRANSFER_GAS_LIMIT,
            nonce_username=old_owner.username,
            tx_value=None,
            function_name="safeTransferFrom",
            input_params=(
                self.collection.network.wrap_in_checksum(old_owner.username),
                self.collection.network.wrap_in_checksum(new_owner),
                self.internal_id,
                int(amount),
                "0x00",
            ),
            input_type=("string", "string", "uint256", "uint256", "string"),
            is1155=True,
        )

    def burn(self, user=None, amount=None):
        if self.standart == "ERC721":
            return self.collection.network.contract_call(
                method_type="write",
                contract_type="erc721main",
                address=self.collection.address,
                gas_limit=TOKEN_MINT_GAS_LIMIT,
                nonce_username=user.username,
                tx_value=None,
                function_name="burn",
                input_params=(self.internal_id,),
                input_type=("uint256",),
                is1155=False,
            )

        return self.collection.network.contract_call(
            method_type="write",
            contract_type="erc1155main",
            address=self.collection.address,
            gas_limit=TOKEN_MINT_GAS_LIMIT,
            nonce_username=user.username,
            tx_value=None,
            function_name="burn",
            input_params=(
                self.collection.network.wrap_in_checksum(user.username),
                self.internal_id,
                int(amount),
            ),
            input_type=("string", "uint256", "uint256"),
            is1155=True,
        )

    def buy_token(
        self, token_amount, buyer, seller=None, price=None, auc=False, bid=None
    ):
        currency = self.currency
        if self.standart == "ERC1155":
            currency = self.ownership_set.filter(owner=seller).first().currency
        fee_address = self.collection.network.get_ethereum_address(currency.fee_address)

        id_order = "0x%s" % secrets.token_hex(32)
        token_count = token_amount

        if self.standart == "ERC721":
            seller_address = self.collection.network.get_ethereum_address(
                self.owner.username
            )
            token_count = 1
        else:
            seller_address = self.collection.network.get_ethereum_address(
                seller.username
            )

        if not price:
            if self.standart == "ERC721":
                price = self.price
            else:
                price = Ownership.objects.get(
                    token=self, owner=seller, selling=True
                ).price
        address = self.collection.network.get_ethereum_address(currency.address)
        creator_address = self.collection.network.get_ethereum_address(
            self.creator.username
        )
        buyer_address = self.collection.network.get_ethereum_address(buyer.username)
        value = 0
        if address.lower() == "0xEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEE".lower():
            value = int(price) * int(token_count)
        total_amount = int(price) * int(token_count)
        types_list = [
            "bytes32",
            "address",
            "address",
            "uint256",
            "uint256",
            "address",
            "uint256",
            "address[]",
            "uint256[]",
            "address",
        ]

        values_list = [
            id_order,
            self.collection.network.wrap_in_checksum(seller_address),
            self.collection.network.wrap_in_checksum(self.collection.ethereum_address),
            self.internal_id,
            token_amount,
            self.collection.network.wrap_in_checksum(address),
            total_amount,
            [
                self.collection.network.wrap_in_checksum(creator_address),
                self.collection.network.wrap_in_checksum(fee_address),
            ],
            [
                (int(self.creator_royalty / 100 * total_amount)),
                (int(currency.service_fee / 100 * total_amount)),
            ],
            self.collection.network.wrap_in_checksum(buyer_address),
        ]
        signature = sign_message(types_list, values_list)

        buyer_nonce = buyer.username
        if auc:
            buyer_nonce = seller_address

        idOrder = id_order
        SellerBuyer = [
            self.collection.network.wrap_in_checksum(seller_address),
            self.collection.network.wrap_in_checksum(buyer_address),
        ]
        if self.collection.network.network_type == "tron":
            tokenToBuy = [
                self.collection.network.wrap_in_checksum(
                    self.collection.ethereum_address
                ),
                self.internal_id,
                token_amount,
            ]
            tokenToSell = [
                self.collection.network.wrap_in_checksum(address),
                0,
                int(total_amount),
            ]
            input_types = (
                "bytes32",
                "address[2]",
                "uint256[3]",
                "uint256[3]",
                "address[]",
                "uint256[]",
                "bytes",
            )

        else:
            tokenToBuy = {
                "tokenAddress": self.collection.network.wrap_in_checksum(
                    self.collection.ethereum_address
                ),
                "id": int(self.internal_id),
                "amount": int(token_amount),
            }
            tokenToSell = {
                "tokenAddress": self.collection.network.wrap_in_checksum(address),
                "id": 0,
                "amount": total_amount,
            }
            input_types = (
                "bytes32",
                "address[2]",
                "tuple",
                "tuple",
                "address[]",
                "uint256[]",
                "bytes",
            )

        feeAddresses = [
            self.collection.network.wrap_in_checksum(creator_address),
            self.collection.network.wrap_in_checksum(fee_address),
        ]
        feeAmounts = [
            (int(self.creator_royalty / 100 * total_amount)),
            (int(currency.service_fee / 100 * total_amount)),
        ]
        signature = signature

        # create tx tracker instance
        if self.standart == "ERC721":
            TransactionTracker.objects.create(token=self, bid=bid)
        else:
            ownership = Ownership.objects.filter(
                token_id=self.id, owner__username__iexact=seller_address
            ).first()
            owner_amount = TransactionTracker.objects.aggregate(
                total_amount=Sum("amount")
            )
            owner_amount = owner_amount["total_amount"] or 0
            if owner_amount and ownership.quantity <= owner_amount + int(token_amount):
                ownership.selling = False
                ownership.save()
            TransactionTracker.objects.create(
                token=self, ownership=ownership, amount=token_amount, bid=bid
            )
        self.selling = False
        self.save()

        return self.collection.network.contract_call(
            method_type="write",
            contract_type="exchange",
            gas_limit=TOKEN_BUY_GAS_LIMIT,
            nonce_username=buyer_nonce,
            tx_value=value,
            function_name=f"makeExchange{self.standart}",
            input_params=(
                idOrder,
                SellerBuyer,
                tokenToBuy,
                tokenToSell,
                feeAddresses,
                feeAmounts,
                signature,
            ),
            input_type=input_types,
        )

    def get_owner_auction(self):
        owners_auction = self.ownership_set.filter(currency_price=None, selling=True)

        owners_auction_info = []
        for owner in owners_auction:
            info = {
                "id": owner.owner.url,
                "name": owner.owner.get_name(),
                "address": owner.owner.username,
                "avatar": owner.owner.avatar,
                "quantity": owner.quantity,
            }
            owners_auction_info.append(info)
        return owners_auction_info


def token_save_dispatcher(sender, instance, created, **kwargs):
    if instance.standart == "ERC1155":
        if not Ownership.objects.filter(token=instance).filter(selling=True):
            instance.selling = False
            instance.currency_price = None
        else:
            instance.selling = True
            try:
                minimal_price = (
                    Ownership.objects.filter(token=instance)
                    .filter(selling=True)
                    .exclude(price=None)
                    .order_by("price")[0]
                    .price
                )
            except Exception:
                minimal_price = None
            instance.currency_price = minimal_price
        post_save.disconnect(token_save_dispatcher, sender=sender)
        instance.save(update_fields=["selling", "currency_price"])
        post_save.connect(token_save_dispatcher, sender=sender)


def default_token_validators(sender, instance, **kwargs):
    matching_token = Token.objects.filter(
        name=instance.name, collection__network=instance.collection.network
    )
    if instance.id:
        matching_token = matching_token.exclude(id=instance.id)
    if matching_token.exists():
        raise ValidationError("Name is occupied")


post_save.connect(token_save_dispatcher, sender=Token)
pre_save.connect(default_token_validators, sender=Token)


class Ownership(models.Model):
    token = models.ForeignKey("Token", on_delete=models.CASCADE)
    owner = models.ForeignKey("accounts.AdvUser", on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(null=True)
    selling = models.BooleanField(default=False)
    currency = models.ForeignKey(
        "rates.UsdRate", on_delete=models.PROTECT, null=True, default=None, blank=True
    )
    currency_price = models.DecimalField(
        max_digits=MAX_AMOUNT_LEN,
        default=None,
        blank=True,
        null=True,
        decimal_places=18,
    )
    currency_minimal_bid = models.DecimalField(
        max_digits=MAX_AMOUNT_LEN,
        default=None,
        blank=True,
        null=True,
        decimal_places=18,
    )

    @property
    def price(self):
        if self.currency_price:
            return int(self.currency_price * self.token.currency.get_decimals)

    @property
    def minimal_bid(self):
        if self.currency_minimal_bid:
            return int(self.currency_minimal_bid * self.token.currency.get_decimals)

    @property
    def get_currency_price(self):
        if self.currency_price:
            return self.price
        return self.minimal_bid

    @property
    def get_price(self):
        if self.price:
            return self.price
        return self.minimal_bid

    @property
    def usd_price(self):
        if self.price:
            return calculate_amount(self.price, self.token.currency.symbol)[0]
        if self.minimal_bid:
            return calculate_amount(self.minimal_bid, self.token.currency.symbol)[0]


class Tags(models.Model):
    name = models.CharField(max_length=30, unique=True)
    icon = models.CharField(max_length=200, blank=True, null=True, default=None)
    banner = models.CharField(max_length=200, blank=True, null=True, default=None)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = "Tags"

    @property
    def ipfs_icon(self):
        if self.icon:
            return "https://ipfs.io/ipfs/{ipfs}".format(ipfs=self.icon)

    @property
    def ipfs_banner(self):
        if self.banner:
            return "https://ipfs.io/ipfs/{ipfs}".format(ipfs=self.banner)


class BidQuerySet(models.QuerySet):
    def committed(self):
        return self.filter(state=Status.COMMITTED)


class BidManager(models.Manager):
    def get_queryset(self):
        return BidQuerySet(self.model, using=self._db)

    def committed(self):
        """Return bids with status committed"""
        return self.get_queryset().committed()


class Bid(models.Model):
    token = models.ForeignKey("Token", on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(null=True)
    user = models.ForeignKey("accounts.AdvUser", on_delete=models.PROTECT)
    amount = models.DecimalField(
        max_digits=MAX_AMOUNT_LEN,
        decimal_places=18,
        default=None,
        blank=True,
        null=True,
    )
    currency = models.ForeignKey(
        "rates.UsdRate", on_delete=models.PROTECT, null=True, blank=True, default=None
    )
    created_at = models.DateTimeField(auto_now_add=True)
    state = models.CharField(
        max_length=50, choices=Status.choices, default=Status.PENDING
    )

    objects = BidManager()

    def __str__(self):
        return f"{self.token} - {self.user}"


class TransactionTracker(models.Model):
    tx_hash = models.CharField(max_length=200, null=True, blank=True)
    token = models.ForeignKey(
        "Token", on_delete=models.CASCADE, null=True, blank=True, default=None
    )
    ownership = models.ForeignKey(
        "Ownership", on_delete=models.CASCADE, null=True, blank=True, default=None
    )
    bid = models.ForeignKey(
        "Bid", on_delete=models.CASCADE, null=True, blank=True, default=None
    )
    amount = models.PositiveSmallIntegerField(null=True, blank=True, default=None)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Tracker hash - {self.tx_hash}"

    @property
    def item(self):
        if self.token:
            return self.token
        return self.ownership


class ViewsTracker(models.Model):
    user_id = models.IntegerField(null=True)
    token = models.ForeignKey("Token", on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
