import logging
import random
from datetime import datetime, timedelta
from decimal import Decimal

from django.core.exceptions import ObjectDoesNotExist
from django.core.mail import send_mail
from django.db.models import Count, OuterRef, Q, Subquery, Sum
from django.utils import timezone
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly
from rest_framework.response import Response
from rest_framework.views import APIView

from src.accounts.models import AdvUser
from src.activity.models import BidsHistory, TokenHistory, UserAction
from src.consts import APPROVE_GAS_LIMIT
from src.networks.models import Network
from src.rates.api import calculate_amount
from src.rates.models import UsdRate
from src.services.search import Search
from src.settings import config
from src.store.api import check_captcha, get_email_connection, validate_bid
from src.store.models import (
    Bid,
    Collection,
    NotableDrop,
    Ownership,
    Status,
    Tags,
    Token,
    TransactionTracker,
    ViewsTracker,
)
from src.store.serializers import (
    BetSerializer,
    BidSerializer,
    CollectionMetadataSerializer,
    CollectionSerializer,
    CollectionSlimSerializer,
    HotCollectionSerializer,
    NotableDropSerializer,
    TagSerializer,
    TokenFullSerializer,
    TokenPatchSerializer,
    TokenSerializer,
    TrendingCollectionSerializer,
)
from src.store.services.collection_import import OpenSeaImport
from src.store.services.ipfs import create_ipfs, send_to_ipfs
from src.store.tasks import import_opensea_collection
from src.utilities import PaginateMixin, sign_message

transfer_tx = openapi.Response(
    description="Response with prepared transfer tx",
    schema=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            "tx": openapi.Schema(type=openapi.TYPE_STRING),
        },
    ),
)


buy_token_response = openapi.Response(
    description="Response with buyed token",
    schema=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            "initial_tx": openapi.Schema(type=openapi.TYPE_OBJECT),
            "nonce": openapi.Schema(type=openapi.TYPE_NUMBER),
            "gasPrice": openapi.Schema(type=openapi.TYPE_NUMBER),
            "gas": openapi.Schema(type=openapi.TYPE_NUMBER),
            "to": openapi.Schema(type=openapi.TYPE_STRING),
            "value": openapi.Schema(type=openapi.TYPE_NUMBER),
            "data": openapi.Schema(type=openapi.TYPE_OBJECT),
            "id_order": openapi.Schema(type=openapi.TYPE_STRING),
            "whoIsSelling": openapi.Schema(type=openapi.TYPE_STRING),
            "tokenToBuy": openapi.Schema(type=openapi.TYPE_OBJECT),
            "amount": openapi.Schema(type=openapi.TYPE_NUMBER),
            "tokenToSell": openapi.Schema(type=openapi.TYPE_OBJECT),
            "tokenAddress": openapi.Schema(type=openapi.TYPE_STRING),
            "id": openapi.Schema(type=openapi.TYPE_NUMBER),
            "feeAddresses": openapi.Schema(
                type=openapi.TYPE_ARRAY, items=openapi.Items(type=openapi.TYPE_STRING)
            ),
            "feeAmount": openapi.Schema(
                type=openapi.TYPE_ARRAY, items=openapi.Items(type=openapi.TYPE_NUMBER)
            ),
            "signature": openapi.Schema(type=openapi.TYPE_STRING),
        },
    ),
)

not_found_response = "user not found"


class SearchView(APIView, PaginateMixin):
    """
    View for search items in shop.
    searching has simple 'contains' logic.
    """

    @swagger_auto_schema(
        operation_description="get search pattern",
        manual_parameters=[
            openapi.Parameter(
                "type",
                openapi.IN_QUERY,
                type=openapi.TYPE_STRING,
                description="Search by: items, users, collections",
            ),
            openapi.Parameter("tags", openapi.IN_QUERY, type=openapi.TYPE_STRING),
            openapi.Parameter(
                "collections", openapi.IN_QUERY, type=openapi.TYPE_STRING
            ),
            openapi.Parameter(
                "is_verified", openapi.IN_QUERY, type=openapi.TYPE_BOOLEAN
            ),
            openapi.Parameter("min_price", openapi.IN_QUERY, type=openapi.TYPE_NUMBER),
            openapi.Parameter("max_price", openapi.IN_QUERY, type=openapi.TYPE_NUMBER),
            openapi.Parameter(
                "order_by",
                openapi.IN_QUERY,
                type=openapi.TYPE_STRING,
                description="For tokens: created_at, price, likes, views, sale, transfer, auction_end, last_sale. \n For users: created, followers, tokens_created",
            ),
            openapi.Parameter(
                "properties",
                openapi.IN_QUERY,
                type=openapi.TYPE_STRING,
                description="JSON in string format, where value is a list. e.g. {value: [1,2]}",
            ),
            openapi.Parameter(
                "rankings",
                openapi.IN_QUERY,
                type=openapi.TYPE_STRING,
                description="JSON in string format. e.g. {value: {min: 1, max: 10}}",
            ),
            openapi.Parameter("on_sale", openapi.IN_QUERY, type=openapi.TYPE_BOOLEAN),
            openapi.Parameter(
                "on_auc_sale", openapi.IN_QUERY, type=openapi.TYPE_BOOLEAN
            ),
            openapi.Parameter(
                "on_timed_auc_sale", openapi.IN_QUERY, type=openapi.TYPE_BOOLEAN
            ),
            openapi.Parameter("currency", openapi.IN_QUERY, type=openapi.TYPE_STRING),
            openapi.Parameter("page", openapi.IN_QUERY, type=openapi.TYPE_NUMBER),
            openapi.Parameter("network", openapi.IN_QUERY, type=openapi.TYPE_STRING),
            openapi.Parameter("creator", openapi.IN_QUERY, type=openapi.TYPE_STRING),
            openapi.Parameter("text", openapi.IN_QUERY, type=openapi.TYPE_STRING),
            openapi.Parameter("owner", openapi.IN_QUERY, type=openapi.TYPE_STRING),
            openapi.Parameter("bids_by", openapi.IN_QUERY, type=openapi.TYPE_STRING),
        ],
        responses={200: TokenSerializer(many=True)},
    )
    def get(self, request):
        params = request.query_params.copy()
        sort = params.pop("type", ["items"])
        sort = sort[0]

        if sort not in config.SEARCH_TYPES.__dict__.keys():
            return Response(
                {"error": "type not found"}, status=status.HTTP_404_NOT_FOUND
            )

        sort_type = getattr(config.SEARCH_TYPES, sort)
        result = Search.get(sort_type).parse(
            current_user=request.user,
            **params,
        )

        return Response(self.paginate(request, result), status=status.HTTP_200_OK)


class CreateView(APIView):
    """
    View for create token transaction.
    """

    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="token_creation",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "name": openapi.Schema(type=openapi.TYPE_STRING),
                "standart": openapi.Schema(type=openapi.TYPE_STRING),
                "total_supply": openapi.Schema(type=openapi.TYPE_NUMBER),
                "currency": openapi.Schema(type=openapi.TYPE_STRING),
                "description": openapi.Schema(type=openapi.TYPE_STRING),
                "price": openapi.Schema(type=openapi.TYPE_NUMBER),
                "minimal_bid": openapi.Schema(type=openapi.TYPE_NUMBER),
                "creator_royalty": openapi.Schema(type=openapi.TYPE_NUMBER),
                "collection": openapi.Schema(type=openapi.TYPE_NUMBER),
                "details": openapi.Schema(type=openapi.TYPE_OBJECT),
                "selling": openapi.Schema(type=openapi.TYPE_STRING),
                "start_auction": openapi.Schema(type=openapi.FORMAT_DATETIME),
                "end_auction": openapi.Schema(type=openapi.FORMAT_DATETIME),
                "digital_key": openapi.Schema(type=openapi.TYPE_STRING),
                "media": openapi.Schema(
                    type=openapi.TYPE_STRING, format=openapi.FORMAT_BINARY
                ),
                "cover": openapi.Schema(
                    type=openapi.TYPE_STRING, format=openapi.FORMAT_BINARY
                ),
                "format": openapi.Schema(type=openapi.TYPE_STRING),
            },
        ),
        responses={200: TokenSerializer, 404: "Collection not found"},
    )
    def post(self, request):
        request_data = request.data
        creator = request.user
        token_collection_id = request_data.get("collection")

        try:
            token_collection = Collection.objects.committed().get_by_short_url(
                token_collection_id
            )
        except Collection.DoesNotExist:
            return Response(
                {"error": "Collection not found"}, status=status.HTTP_404_NOT_FOUND
            )

        standart = token_collection.standart

        if Token.objects.filter(collection__network=token_collection.network).filter(
            name=request_data.get("name")
        ):
            return Response(
                {"name": "name already used"}, status=status.HTTP_400_BAD_REQUEST
            )

        ipfs = create_ipfs(request)
        type_ = ["address", "string"]
        msg = [
            token_collection.network.wrap_in_checksum(
                token_collection.ethereum_address
            ),
            ipfs,
        ]
        amount = request_data.get("total_supply")
        if standart == "ERC1155":
            if not amount:
                return Response(
                    {"amount": "supply not specified "}, status=status.HTTP_400_BAD_REQUEST
                )
            type_.append("uint256")
            msg.append(int(amount))
        signature = sign_message(type_, msg)

        initial_tx = token_collection.create_token(creator, ipfs, signature, amount)

        token = Token()
        token.save_in_db(request, ipfs)

        response_data = {"initial_tx": initial_tx, "token": TokenSerializer(token).data}
        return Response(response_data, status=status.HTTP_200_OK)


class CreateCollectionView(APIView):
    """
    View for create collection transaction..
    """

    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="collection_creation",
        manual_parameters=[
            openapi.Parameter("network", openapi.IN_QUERY, type=openapi.TYPE_STRING),
        ],
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "name": openapi.Schema(type=openapi.TYPE_STRING),
                "standart": openapi.Schema(type=openapi.TYPE_STRING),
                "avatar": openapi.Schema(
                    type=openapi.TYPE_STRING, format=openapi.FORMAT_BINARY
                ),
                "symbol": openapi.Schema(type=openapi.TYPE_STRING),
                "description": openapi.Schema(type=openapi.TYPE_STRING),
                "short_url": openapi.Schema(type=openapi.TYPE_STRING),
                "site": openapi.Schema(type=openapi.TYPE_STRING),
                "discord": openapi.Schema(type=openapi.TYPE_STRING),
                "twitter": openapi.Schema(type=openapi.TYPE_STRING),
                "instagram": openapi.Schema(type=openapi.TYPE_STRING),
                "medium": openapi.Schema(type=openapi.TYPE_STRING),
                "telegram": openapi.Schema(type=openapi.TYPE_STRING),
                "is_nsfw": openapi.Schema(type=openapi.TYPE_BOOLEAN),
                "display_theme": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="Padded, Contained, Covered",
                ),
            },
            required=["name", "creator", "avatar", "symbol", "standart"],
        ),
    )
    def post(self, request):
        name = request.data.get("name")
        symbol = request.data.get("symbol")
        short_url = request.data.get("short_url")
        standart = request.data.get("standart")
        network = request.query_params.get("network", config.DEFAULT_NETWORK)
        owner = request.user

        is_unique, response = Collection.collection_is_unique(
            name, symbol, short_url, network
        )
        if not is_unique:
            return response

        if standart not in ["ERC721", "ERC1155"]:
            return Response(
                "invalid collection type",
                status=status.HTTP_400_BAD_REQUEST,
            )
        if short_url and Collection.objects.filter(short_url=short_url).exists():
            return Response(
                {"error": "short_url already created"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        network = Network.objects.filter(name__icontains=network)
        if not network:
            return Response("invalid network name", status=status.HTTP_404_NOT_FOUND)

        initial_tx = Collection.create_contract(
            name, symbol, standart, owner, network.first()
        )

        collection = Collection()

        media = request.FILES.get("avatar")
        cover = request.FILES.get("cover")
        if media:
            ipfs = send_to_ipfs(media)
        else:
            ipfs = None
        if cover:
            cover = send_to_ipfs(cover)
        else:
            cover = None
        collection.save_in_db(request, ipfs, cover)
        response_data = {
            "initial_tx": initial_tx,
            "collection": CollectionSlimSerializer(collection).data,
        }
        return Response(response_data, status=status.HTTP_200_OK)


class GetLikedView(APIView, PaginateMixin):
    """
    View for getting all items liked by address
    """

    @swagger_auto_schema(
        operation_description="get tokens liked by address",
        responses={200: TokenSerializer(many=True), 404: not_found_response},
        manual_parameters=[
            openapi.Parameter("network", openapi.IN_QUERY, type=openapi.TYPE_STRING),
            openapi.Parameter("page", openapi.IN_QUERY, type=openapi.TYPE_NUMBER),
        ],
    )
    def get(self, request, user_id):
        network = request.query_params.get("network", config.DEFAULT_NETWORK)
        try:
            user = AdvUser.objects.get_by_custom_url(user_id)
        except ObjectDoesNotExist:
            return Response(
                {"error": not_found_response}, status=status.HTTP_404_NOT_FOUND
            )

        # get users associated with the model UserAction
        ids = user.followers.all().values_list("user")

        # get tokens that users like
        tokens_action = UserAction.objects.filter(method="like", user__in=ids).order_by(
            "-date"
        )

        tokens = [action.token for action in tokens_action]
        if network:
            tokens = [
                token
                for token in tokens
                if network.lower() in token.collection.network.name.lower()
            ]

        tokens = TokenSerializer(tokens, many=True, context={"user": request.user}).data
        return Response(self.paginate(request, tokens), status=status.HTTP_200_OK)


class GetView(APIView):
    """
    View for get token info.
    """

    permission_classes = [IsAuthenticatedOrReadOnly]

    @swagger_auto_schema(
        operation_description="get token info",
        responses={200: TokenFullSerializer, 404: "token not found"},
    )
    def get(self, request, id):
        try:
            token = Token.objects.committed().get(id=id)
        except ObjectDoesNotExist:
            return Response({"token not found"}, status=status.HTTP_404_NOT_FOUND)

        if request.user:
            ViewsTracker.objects.get_or_create(token=token, user_id=request.user.id)

        response_data = TokenFullSerializer(token, context={"user": request.user}).data
        return Response(response_data, status=status.HTTP_200_OK)

    @swagger_auto_schema(
        operation_description="update owned token info",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "selling": openapi.Schema(type=openapi.TYPE_BOOLEAN),
                "minimal_bid": openapi.Schema(type=openapi.TYPE_NUMBER),
                "price": openapi.Schema(type=openapi.TYPE_NUMBER),
                "currency": openapi.Schema(type=openapi.TYPE_STRING),
                "start_auction": openapi.Schema(type=openapi.FORMAT_DATETIME),
                "end_auction": openapi.Schema(type=openapi.FORMAT_DATETIME),
            },
        ),
        responses={
            200: TokenFullSerializer,
            404: "token not found",
            400: "this token doesn't belong to you",
        },
    )
    def patch(self, request, id):
        request_data = request.data.copy()
        user = request.user

        try:
            token = Token.objects.committed().get(id=id)
        except ObjectDoesNotExist:
            return Response(
                {"error: token not found"}, status=status.HTTP_404_NOT_FOUND
            )

        is_valid, response = token.is_valid(user)
        if not is_valid:
            return response
        price = request_data.get("price", None)
        minimal_bid = request_data.get("minimal_bid", None)
        start_auction = request_data.get("start_auction")
        end_auction = request_data.get("end_auction")
        selling = request_data.get("selling", True)
        currency = request_data.get("currency")

        if price:  # instance sale
            request_data.pop("price", None)
            price = Decimal(str(price))
        elif (
            currency == "0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee" and selling
        ):  # auction sale
            return Response(
                {"error": "Invalid currency"}, status=status.HTTP_400_BAD_REQUEST
            )

        request_data["currency_price"] = price
        if minimal_bid:
            request_data.pop("minimal_bid")
            minimal_bid = Decimal(str(minimal_bid))
            price = minimal_bid
        request_data["currency_minimal_bid"] = minimal_bid

        if currency:
            currency = UsdRate.objects.filter(
                symbol=currency, network=token.collection.network
            ).first()
            if not currency:
                return Response(
                    {"error": "Currency not found"}, status=status.HTTP_404_NOT_FOUND
                )

        if token.standart == "ERC721":
            old_price = token.currency_price
            amount = 1

            if start_auction:
                request_data["start_auction"] = datetime.fromtimestamp(
                    int(start_auction)
                )
            else:
                request_data.pop("start_auction", None)
            if end_auction:
                request_data["end_auction"] = datetime.fromtimestamp(int(end_auction))
            else:
                request_data.pop("end_auction", None)
            serializer = TokenPatchSerializer(token, data=request_data, partial=True)

            logging.info(f"PatchSerializer valid - {serializer.is_valid()}")
            if serializer.is_valid():
                serializer.save()
        else:
            ownership = Ownership.objects.get(owner=user, token=token)
            old_price = ownership.currency_price
            amount = ownership.quantity
            ownership.selling = selling
            ownership.currency = currency
            ownership.currency_price = price
            ownership.currency_minimal_bid = minimal_bid
            ownership.full_clean()
            ownership.save()

        new_price = price or minimal_bid
        # add changes to listing
        if new_price and new_price != old_price:
            TokenHistory.objects.create(
                token=token,
                old_owner=user,
                currency=currency,
                amount=amount,
                price=new_price,
                method="Listing",
            )

        response_data = TokenFullSerializer(token, context={"user": request.user}).data
        return Response(response_data, status=status.HTTP_200_OK)


class TokenBurnView(APIView):
    """
    View for burn token.
    """

    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="token burn",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "amount": openapi.Schema(type=openapi.TYPE_NUMBER),
            },
        ),
        responses={200: transfer_tx, 404: "token does not exist"},
    )
    def post(self, request, token_id):
        user = request.user
        try:
            token = Token.objects.committed().get(id=token_id)
        except ObjectDoesNotExist:
            return Response({"token does not exist"}, status=status.HTTP_404_NOT_FOUND)
        amount = request.data.get("amount")
        is_valid, res = token.is_valid(user=user)
        if not is_valid:
            return res
        return Response(
            {"initial_tx": token.burn(user, amount)}, status=status.HTTP_200_OK
        )


class GetHotView(APIView, PaginateMixin):
    """
    View for getting hot items
    """

    @swagger_auto_schema(
        operation_description="get hot tokens",
        responses={200: TokenFullSerializer(many=True), 404: "Token not found"},
        manual_parameters=[
            openapi.Parameter("sort", openapi.IN_QUERY, type=openapi.TYPE_STRING),
            openapi.Parameter("tag", openapi.IN_QUERY, type=openapi.TYPE_STRING),
        ],
    )
    def get(self, request):
        sort = request.query_params.get("sort", "recent")
        tag = request.query_params.get("tag")
        network = request.query_params.get("network", config.DEFAULT_NETWORK)
        order = getattr(config.SORT_STATUSES, sort)
        tokens = Token.objects.committed().network(network)
        if tag:
            tokens = tokens.filter(tags__name__contains=tag).order_by(order)
        else:
            tokens = tokens.order_by(order)
        if sort in ("cheapest", "highest"):
            tokens = tokens.exclude(price=None).exclude(selling=False)
        tokens = TokenFullSerializer(
            tokens, context={"user": request.user}, many=True
        ).data
        return Response(self.paginate(request, tokens), status=status.HTTP_200_OK)


class GetHotCollectionsView(APIView):
    """
    View for getting hot collections
    """

    @swagger_auto_schema(
        operation_description="get hot collections",
        manual_parameters=[
            openapi.Parameter("network", openapi.IN_QUERY, type=openapi.TYPE_STRING),
        ],
        responses={200: HotCollectionSerializer(many=True)},
    )
    def get(self, request):
        network = request.query_params.get("network", config.DEFAULT_NETWORK)
        collections = (
            Collection.objects.committed().hot_collections(network).order_by("-id")[:5]
        )
        response_data = HotCollectionSerializer(collections, many=True).data
        return Response(response_data, status=status.HTTP_200_OK)


class GetCollectionView(APIView):
    """
    View for get collection info in shop.
    """

    @swagger_auto_schema(
        operation_description="get collection info",
        manual_parameters=[
            openapi.Parameter("network", openapi.IN_QUERY, type=openapi.TYPE_STRING),
            openapi.Parameter("page", openapi.IN_QUERY, type=openapi.TYPE_NUMBER),
        ],
        responses={200: CollectionSerializer, 400: "collection not found"},
    )
    def get(self, request, param):
        try:
            collection = Collection.objects.committed().get_by_short_url(param)
        except Collection.DoesNotExist:
            return Response(
                {"error": "collection not found"},
                status=status.HTTP_404_NOT_FOUND,
            )
        response_data = CollectionSerializer(collection).data
        return Response(response_data, status=status.HTTP_200_OK)


class TransferOwned(APIView):
    """
    View for tansfering token owned by user.
    """

    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="transfer_owned",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "address": openapi.Schema(type=openapi.TYPE_STRING),
                "amount": openapi.Schema(type=openapi.TYPE_NUMBER),
            },
        ),
        responses={
            200: transfer_tx,
            400: "you can not transfer tokens that don't belong to you",
            404: "token not found",
        },
    )
    def post(self, request, token):
        address = request.data.get("address")
        amount = request.data.get("amount")
        user = request.user
        try:
            transferring_token = Token.objects.get(id=token)
        except ObjectDoesNotExist:
            return Response(
                {"error": "token not found"}, status=status.HTTP_404_NOT_FOUND
            )

        is_valid, response = transferring_token.is_valid(user=user)
        if not is_valid:
            return response

        initial_tx = transferring_token.transfer(user, address, amount)
        return Response({"initial_tx": initial_tx}, status=status.HTTP_200_OK)


class BuyTokenView(APIView):
    """
    view to buy a token
    """

    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="buy_token",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "id": openapi.Schema(type=openapi.TYPE_NUMBER),
                "tokenAmount": openapi.Schema(type=openapi.TYPE_NUMBER),
                "sellerId": openapi.Schema(type=openapi.TYPE_STRING),
            },
        ),
        responses={
            200: buy_token_response,
            400: "you cant buy token",
            404: "token with given id was not found",
        },
    )
    def post(self, request):
        buyer = request.user
        seller_id = request.data.get("sellerId")
        token_id = request.data.get("id")
        token_amount = request.data.get("tokenAmount")

        if token_id is None:
            return Response(
                {"error": "invalid token_id"}, status=status.HTTP_400_BAD_REQUEST
            )
        if token_amount is None:
            return Response(
                {"error": "invalid token_amount"}, status=status.HTTP_400_BAD_REQUEST
            )

        token_id = int(token_id)
        token_amount = int(token_amount)
        try:
            tradable_token = Token.objects.get(id=token_id)
        except ObjectDoesNotExist:
            Response(
                {"error": "token with given id was not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        is_valid, response = tradable_token.is_valid_for_buy(token_amount, seller_id)
        if not is_valid:
            return response

        buyer = request.user
        try:
            if seller_id:
                seller = AdvUser.objects.get_by_custom_url(seller_id)
                ownership = Ownership.objects.filter(
                    token__id=token_id, owner=seller
                ).filter(selling=True)
                if not ownership:
                    return Response(
                        {"error": "user is not owner or token is not on sell"},
                        status=status.HTTP_404_NOT_FOUND,
                    )
            else:
                seller = None
        except ObjectDoesNotExist:
            return Response(
                {"error": "user not found"}, status=status.HTTP_404_NOT_FOUND
            )

        buy = tradable_token.buy_token(token_amount, buyer, seller)
        return Response({"initial_tx": buy}, status=status.HTTP_200_OK)


@api_view(http_method_names=["GET"])
def get_tags(request):
    tags = Tags.objects.all().order_by("id")
    return Response(TagSerializer(tags, many=True).data, status=status.HTTP_200_OK)


class MakeBid(APIView):
    """
    view for making bid on auction
    """

    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="make_bid",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "token_id": openapi.Schema(type=openapi.TYPE_NUMBER),
                "amount": openapi.Schema(type=openapi.TYPE_NUMBER),
                "quantity": openapi.Schema(type=openapi.TYPE_NUMBER),
            },
        ),
        responses={
            400: "error",
            404: "token not found",
        },
    )
    def post(self, request):
        request_data = request.data
        token_id = request_data.get("token_id")
        amount = Decimal(str(request_data.get("amount")))
        quantity = int(request_data.get("quantity"))
        try:
            token = Token.objects.get(id=token_id)
        except ObjectDoesNotExist:
            return Response(
                {"error": "Token not found"},
                status=status.HTTP_404_NOT_FOUND,
            )
        user = request.user

        network = token.collection.network
        currency = UsdRate.objects.filter(
            symbol=f"w{network.native_symbol}".lower(),
            network=network,
        ).first()
        if not currency:
            return Response(
                {"error": "Currency not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # returns OK if valid, or error message
        result = validate_bid(user, token_id, amount, quantity)

        if result != "OK":
            return Response({"error": result}, status=status.HTTP_400_BAD_REQUEST)

        # create new bid or update old one
        bid, created = Bid.objects.get_or_create(user=user, token=token)

        if not created and bid.amount >= amount:
            return Response(
                {"error": "you cannot lower your bid"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        bid.amount = amount
        bid.quantity = quantity
        bid.full_clean()
        bid.save()

        # construct approve tx if not approved yet:
        allowance = network.contract_call(
            method_type="read",
            contract_type="token",
            address=currency.address,
            function_name="allowance",
            input_params=(
                token.collection.network.wrap_in_checksum(user.username),
                network.exchange_address,
            ),
            input_type=("address", "address"),
            output_types=("uint256",),
        )

        user_balance = network.contract_call(
            method_type="read",
            contract_type="token",
            address=currency.address,
            function_name="balanceOf",
            input_params=(network.wrap_in_checksum(user.username),),
            input_type=("address",),
            output_types=("uint256",),
        )

        amount, _ = calculate_amount(amount, currency.symbol)

        if allowance < amount * quantity:

            initial_tx = network.contract_call(
                method_type="write",
                contract_type="token",
                address=currency.address,
                gas_limit=APPROVE_GAS_LIMIT,
                nonce_username=user.username,
                tx_value=None,
                function_name="approve",
                input_params=(
                    network.wrap_in_checksum(network.exchange_address),
                    user_balance,
                ),
                input_type=("address", "uint256"),
            )

            return Response({"initial_tx": initial_tx}, status=status.HTTP_200_OK)

        bid.state = Status.COMMITTED
        bid.full_clean()
        bid.save()

        BidsHistory.objects.create(
            token=bid.token,
            user=bid.user,
            price=bid.amount,
            date=bid.created_at,
        )

        return Response(
            {"bid created, allowance not needed"}, status=status.HTTP_200_OK
        )


@api_view(http_method_names=["GET"])
@permission_classes([IsAuthenticated])
def get_bids(request, token_id):
    # validating token and user
    try:
        token = Token.objects.committed().get(id=token_id)
    except ObjectDoesNotExist:
        return Response({"error": "token not found"}, status=status.HTTP_404_NOT_FOUND)
    if token.is_auc_selling:
        return Response(
            {"error": "token is not set on auction"}, status=status.HTTP_400_BAD_REQUEST
        )
    user = request.user
    if token.owner != user:
        return Response(
            {"error": "you can get bids list only for owned tokens"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    bids = Bid.objects.filter(token=token)

    response_data = BidSerializer(bids, many=True).data
    return Response(response_data, status=status.HTTP_200_OK)


class VerificateBetView(APIView):
    @swagger_auto_schema(
        operation_description="verificate bet",
        responses={200: BetSerializer, 404: "token or bid not found"},
    )
    def get(self, request, token_id):
        try:
            token = Token.objects.get(id=token_id)
        except ObjectDoesNotExist:
            return Response(
                {"error": "token not found"}, status=status.HTTP_404_NOT_FOUND
            )
        bets = Bid.objects.filter(token=token).order_by("-amount")
        max_bet = bets.first()
        if not max_bet:
            return Response(
                {"invalid_bet": None, "valid_bet": None}, status=status.HTTP_200_OK
            )

        user = max_bet.user
        amount = max_bet.amount
        quantity = max_bet.quantity

        check_valid = validate_bid(user, token_id, amount, quantity)

        if check_valid == "OK":
            logging.info("all ok!")
            return Response(BetSerializer(max_bet).data, status=status.HTTP_200_OK)
        else:
            logging.info("not ok(")
            max_bet.delete()
            logging.info(bets)
            for bet in bets:
                user = bet.user
                amount = bet.amount
                quantity = bet.quantity
                check_valid = validate_bid(user, token_id, amount, quantity)
                if check_valid == "OK":
                    logging.info("again ok!")
                    return Response(
                        {
                            "invalid_bet": BetSerializer(max_bet).data,
                            "valid_bet": BetSerializer(bet).data,
                        },
                        status=status.HTTP_200_OK,
                    )
                else:
                    bet.delete()
                    continue
            return Response(
                {"invalid_bet": BetSerializer(max_bet).data, "valid_bet": None},
                status=status.HTTP_200_OK,
            )


class AuctionEndView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="end if auction and take the greatest bet",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={"token": openapi.Schema(type=openapi.TYPE_STRING)},
        ),
        responses={
            200: buy_token_response,
            400: "cant sell token",
            404: "no active bids",
        },
    )
    def post(self, request, token_id):

        bet = Bid.objects.filter(token__id=token_id).order_by("-amount").first()
        if not bet:
            return Response(
                {"error": "no active bids"}, status=status.HTTP_NOT_FOUND_404
            )

        token = bet.token
        buyer = bet.user
        price = bet.amount * bet.token.currency.get_decimals

        seller = request.user
        if token.standart == "ERC721":
            if seller != token.owner:
                return Response(
                    {"error": "user is not owner or token is not on sell"},
                    status=status.HTTP_BAD_REQUEST_400,
                )
        else:
            ownership = Ownership.objects.filter(
                token=token,
                owner=seller,
                selling=True,
                currency_minimal_bid__isnull=False,
            ).first()
            if not ownership:
                return Response(
                    {"error": "user is not owner or token is not on sell"},
                    status=status.HTTP_BAD_REQUEST_400,
                )

        if token.standart == "ERC721":
            token_amount = 0
        else:
            token_amount = min(bet.quantity, ownership.quantity)

        sell = token.buy_token(
            token_amount, buyer, seller=seller, price=price, auc=True
        )
        return Response({"initial_tx": sell}, status=status.HTTP_200_OK)


class ReportView(APIView):
    @swagger_auto_schema(
        operation_description="report page",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "page": openapi.Schema(type=openapi.TYPE_STRING),
                "message": openapi.Schema(type=openapi.TYPE_STRING),
                "token": openapi.Schema(type=openapi.TYPE_STRING),
            },
        ),
        responses={200: "your report sent to admin", 400: "report not sent to admin"},
    )
    def post(self, request):
        """
        view for report form
        """
        request_data = request.data
        page = request_data.get("page")
        message = request_data.get("message")
        response = request_data.get("token")

        if config.CAPTCHA_SECRET:
            if not check_captcha(response):
                return Response(
                    "you are robot. go away, robot!", status=status.HTTP_400_BAD_REQUEST
                )

        connection = get_email_connection()
        text = """
                Page: {page}
                Message: {message}
                """.format(
            page=page, message=message
        )

        send_mail(
            f"Report from {config.TITLE}",
            text,
            config.HOST_USER,
            [config.MAIL],
            connection=connection,
        )
        logging.info("message sent")

        return Response("OK", status=status.HTTP_200_OK)


class SetCoverView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="set cover",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "id": openapi.Schema(type=openapi.TYPE_NUMBER),
                "cover": openapi.Schema(
                    type=openapi.TYPE_STRING, format=openapi.FORMAT_BINARY
                ),
            },
        ),
        responses={200: "OK", 400: "error"},
    )
    def post(self, request):
        user = request.user
        collection_id = request.data.get("id")
        try:
            collection = Collection.objects.committed().get_by_short_url(collection_id)
        except ObjectDoesNotExist:
            return Response(
                {"error": "collection not found"}, status=status.HTTP_404_NOT_FOUND
            )
        if collection.creator != user:
            return Response(
                {"error": "you can set covers only for your collections"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        media = request.FILES.get("cover")
        if media:
            ipfs = send_to_ipfs(media)
            collection.cover_ipfs = ipfs
            collection.save()
        return Response(collection.cover, status=status.HTTP_200_OK)


@api_view(http_method_names=["GET"])
def get_fee(request):
    currency_symbol = request.query_params.get("currency")
    try:
        currency = UsdRate.objects.get(symbol=currency_symbol)
    except ObjectDoesNotExist:
        return Response(
            {"error": "currency rate not found"}, status=status.HTTP_404_NOT_FOUND
        )

    return Response(currency.service_fee, status=status.HTTP_200_OK)


@swagger_auto_schema(
    methods=["get"],
    manual_parameters=[
        openapi.Parameter("network", openapi.IN_QUERY, type=openapi.TYPE_STRING),
    ],
    responses={200: TokenSerializer, 404: "Tokens not found"},
)
@api_view(http_method_names=["GET"])
def get_random_token(request):
    network = request.query_params.get("network", config.DEFAULT_NETWORK)
    token_list = (
        Token.objects.committed()
        .network(network)
        .filter(Q(owner__is_verificated=True) | Q(owners__is_verificated=True))
    )
    if not token_list.exists():
        return Response("Tokens not found", status=status.HTTP_404_NOT_FOUND)
    token = random.choice(token_list)
    response_data = TokenSerializer(token).data
    return Response(response_data, status=status.HTTP_200_OK)


@api_view(http_method_names=["GET"])
def get_favorites(request):
    network = request.query_params.get("network", config.DEFAULT_NETWORK)
    token_list = (
        Token.objects.committed()
        .network(network)
        .filter(is_favorite=True)
        .order_by("-updated_at")
    )
    if not token_list.exists():
        return Response("Tokens not found", status=status.HTTP_404_NOT_FOUND)
    tokens = TokenFullSerializer(
        token_list, many=True, context={"user": request.user}
    ).data
    response_data = [token for token in tokens if token.get("available")]
    return Response(response_data, status=status.HTTP_200_OK)


@api_view(http_method_names=["GET"])
def get_hot_bids(request):
    network = request.query_params.get("network", config.DEFAULT_NETWORK)
    bids = (
        Bid.objects.filter(state=Status.COMMITTED)
        .filter(token__collection__network__name__icontains=network)
        .distinct("token")[:6]
    )
    if not bids.exists():
        return Response("No bids found", status=status.HTTP_404_NOT_FOUND)
    token_list = [bid.token for bid in bids]
    response_data = TokenFullSerializer(
        token_list, context={"user": request.user}, many=True
    ).data
    return Response(response_data, status=status.HTTP_200_OK)


class SupportView(APIView):
    @swagger_auto_schema(
        operation_description="support view",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "email": openapi.Schema(type=openapi.TYPE_STRING),
                "message": openapi.Schema(type=openapi.TYPE_STRING),
                "token": openapi.Schema(type=openapi.TYPE_STRING),
            },
        ),
        responses={200: "your report sent to admin", 400: "report not sent to admin"},
    )
    def post(self, request):
        """
        view for report form
        """
        request_data = request.data
        email = request_data.get("email")
        message = request_data.get("message")
        response = request_data.get("token")

        if config.CAPTCHA_SECRET:
            if not check_captcha(response):
                return Response(
                    "you are robot. go away, robot!", status=status.HTTP_400_BAD_REQUEST
                )

        connection = get_email_connection()
        text = """
                Email: {email}
                Message: {message}
                """.format(
            email=email, message=message
        )

        send_mail(
            f"Support form from {config.TITLE}",
            text,
            config.HOST_USER,
            [config.MAIL],
            connection=connection,
        )
        logging.info("message sent")

        return Response("OK", status=status.HTTP_200_OK)


class TransactionTrackerView(APIView):
    """
    View for transaction tracking
    """

    @swagger_auto_schema(
        operation_description="transaction_tracker",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "tx_hash": openapi.Schema(type=openapi.TYPE_STRING),
                "token": openapi.Schema(type=openapi.TYPE_NUMBER),
                "ownership": openapi.Schema(type=openapi.TYPE_STRING),
                "amount": openapi.Schema(type=openapi.TYPE_NUMBER),
            },
        ),
    )
    def post(self, request):
        token_id = request.data.get("token")
        tx_hash = request.data.get("tx_hash")
        amount = request.data.get("amount", 1)
        bid_id = request.data.get("bid_id")

        token = Token.objects.filter(id=token_id).first()
        if not token:
            return Response(
                {"error": "token with given id not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        bid = None
        if bid_id:
            bid = Bid.objects.filter(id=bid_id).first()
            if not bid:
                return Response(
                    {"error": "bid not found"}, status=status.HTTP_404_NOT_FOUND
                )

        if token.standart == "ERC721":
            tracker = TransactionTracker.objects.filter(token=token, bid=bid).first()
        else:
            owner_url = request.data.get("ownership")
            try:
                user = AdvUser.objects.get_by_custom_url(owner_url)
            except ObjectDoesNotExist:
                return Response(
                    {"error": "wrong owner url"}, status=status.HTTP_404_NOT_FOUND
                )
            ownership = Ownership.objects.filter(token_id=token_id, owner=user).first()
            owner_amount = TransactionTracker.objects.aggregate(
                total_amount=Sum("amount")
            )
            owner_amount = owner_amount["total_amount"] or 0
            if owner_amount and ownership.quantity <= owner_amount + int(amount):
                ownership.selling = False
                ownership.save()
            tracker = TransactionTracker.objects.filter(
                token=token, ownership=ownership, amount=amount, bid=bid
            ).first()
        if tracker:
            tracker.tx_hash = tx_hash
            tracker.save()
            return Response(
                {"success": "transaction is tracked"}, status=status.HTTP_200_OK
            )
        return Response({"tracker not found"}, status=status.HTTP_404_NOT_FOUND)


class GetCollectionByAdressView(APIView):
    """
    View for get collection metadata by adress.
    """

    @swagger_auto_schema(
        operation_description="get collection metadata by adress",
        responses={200: CollectionMetadataSerializer, 404: "collection not found"},
    )
    def get(self, request, address):
        try:
            collection = Collection.objects.committed().get(address__iexact=address)
        except ObjectDoesNotExist:
            return Response(
                {"error": "collection not found"}, status=status.HTTP_404_NOT_FOUND
            )

        response_data = CollectionMetadataSerializer(collection).data
        return Response(response_data, status=status.HTTP_200_OK)


def get_token_max_price(token):
    if not (token.is_selling or token.is_auc_selling):
        return 0
    if token.standart == "ERC721":
        return (
            token.currency_price if token.currency_price else token.currency_minimal_bid
        )
    owners = token.ownership_set.all()
    prices = [
        owner.currency_price if owner.currency_price else owner.currency_minimal_bid
        for owner in owners
        if owner.selling
    ]
    return max(prices)


@api_view(http_method_names=["GET"])
def get_max_price(request):
    network = request.query_params.get("network", config.DEFAULT_NETWORK)
    currency = request.query_params.get("currency")
    tokens = (
        Token.objects.committed().network(network).filter(currency__symbol=currency)
    )
    token_prices = [get_token_max_price(t) for t in tokens]
    max_price = 100
    if token_prices:
        max_price = max(token_prices)
    return Response({"max_price": max_price}, status=status.HTTP_200_OK)


class GetMostBiddedView(APIView):
    """
    View for get info for token with most bid count.
    """

    # permission_classes = [IsAuthenticatedOrReadOnly]
    @swagger_auto_schema(
        operation_description="get hot auction",
        responses={200: TokenFullSerializer, 404: "tokens not found"},
    )
    def get(self, request):
        tokens = (
            Token.objects.committed()
            .annotate(bid_count=Count("bid"))
            .filter(bid_count__gt=0)
            .order_by("-bid_count")[:5]
        )
        if not tokens:
            return Response("tokens not found", status=status.HTTP_404_NOT_FOUND)
        response_data = TokenFullSerializer(
            tokens, many=True, context={"user": request.user}
        ).data
        return Response(response_data, status=status.HTTP_200_OK)


class GetRelatedView(APIView):
    """
    View for get info for token related to id.
    """

    permission_classes = [IsAuthenticatedOrReadOnly]

    @swagger_auto_schema(
        operation_description="get related",
        responses={200: TokenSerializer, 404: "token not found"},
    )
    def get(self, request, id):
        try:
            token = Token.objects.committed().get(id=id)
        except ObjectDoesNotExist:
            return Response("token not found", status=status.HTTP_404_NOT_FOUND)
        random_related = (
            Token.objects.committed()
            .filter(collection=token.collection)
            .exclude(id=id)
            .distinct()
        )
        if random_related:
            random_related = random.choices(random_related, k=4)
            random_related = set(
                random_related
            )  # if count of tokens is less than k, the list will contain duplicate
        response_data = TokenSerializer(
            random_related, many=True, context={"user": request.user}
        ).data
        return Response(response_data, status=status.HTTP_200_OK)


class RemoveRejectView(APIView):
    """
    View for remove rejected token or collection by id.
    """

    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Remove rejected token or collection",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "id": openapi.Schema(type=openapi.TYPE_NUMBER),
                "type": openapi.Schema(type=openapi.TYPE_STRING),
            },
        ),
        responses={200: "success"},
    )
    def post(self, request):
        items = {
            "token": Token,
            "collection": Collection,
        }
        item_id = request.data.get("id")
        item_type = request.data.get("type")
        if item_type not in ["token", "collection"]:
            return Response(
                {"error": "Item type should be 'token' or 'collection'"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        items[item_type].objects.filter(status=Status.PENDING, id=item_id).delete()
        return Response("success", status=status.HTTP_200_OK)


@api_view(http_method_names=["GET"])
def get_total_count(request):
    tokens_count = Token.objects.committed().count()
    verified_users_count = AdvUser.objects.filter(is_verificated=True).count()
    collections_count = Collection.objects.filter(is_default=False).count()
    time_delta = timezone.now() - timedelta(days=1)
    users_active_daily = AdvUser.objects.filter(last_login__gte=time_delta).count()
    response_data = {
        "total_tokens": tokens_count,
        "total_collections": collections_count,
        "verified_users": verified_users_count,
        "users_active_daily": users_active_daily,
    }
    return Response(response_data, status=status.HTTP_200_OK)


@swagger_auto_schema(
    method="get",
    manual_parameters=[
        openapi.Parameter("tag", openapi.IN_QUERY, type=openapi.TYPE_STRING),
        openapi.Parameter("network", openapi.IN_QUERY, type=openapi.TYPE_STRING),
    ],
    operation_description="Trending collections",
    responses={200: TrendingCollectionSerializer(many=True)},
)
@api_view(http_method_names=["GET"])
def trending_collections(request):
    tag = request.query_params.get("tag")
    network = request.query_params.get("network")

    tracker_time = timezone.now() - timedelta(days=config.TRENDING_TRACKER_TIME)

    tracker = (
        ViewsTracker.objects.filter(created_at__gte=tracker_time)
        .filter(token=OuterRef("id"))
        .values("token")
        .annotate(views_=Count("id"))
    )

    tokens = (
        Token.objects.filter(collection=OuterRef("id"))
        .annotate(views_=Subquery(tracker.values("views_")[:1]))
        .values("collection")
        .annotate(views=Sum("views_"))
    )
    collections = (
        Collection.objects.network(network)
        .tag(tag)
        .filter(is_default=False)
        .annotate(views=Subquery(tokens.values("views")[:1]))
    ).order_by("-views")
    collections = [col for col in collections if col.views][:12]
    return Response(
        TrendingCollectionSerializer(collections, many=True).data,
        status=status.HTTP_200_OK,
    )


class CollectionImportView(APIView):
    """
    View for import contracts
    """

    @swagger_auto_schema(
        operation_description="Import 721 ethereum collection from opensea",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "collection": openapi.Schema(type=openapi.TYPE_STRING),
            },
        ),
        responses={200: "success"},
    )
    def post(self, request):
        collection_address = request.data.get("collection")
        network_name = "ethereum"
        network = Network.objects.filter(name__iexact=network_name).first()

        collection_import = OpenSeaImport(collection_address, network)

        collection = collection_import.get_collection_data()
        if not collection:
            return Response(
                {"error": "Collection not found"}, status=status.HTTP_400_BAD_REQUEST
            )

        if not collection.get("stats").get("count", 0):
            return Response(
                {"error": "Collection error"}, status=status.HTTP_400_BAD_REQUEST
            )

        standart = collection.get("primary_asset_contracts")[0].get("schema_name")
        if standart not in ["ERC1155", "ERC721"]:
            return Response(
                {"error": "Bad collection standart"}, status=status.HTTP_400_BAD_REQUEST
            )

        import_opensea_collection.delay(collection_address, network_name, collection)

        return Response("success", status=status.HTTP_200_OK)


class NotableDropView(APIView):
    @swagger_auto_schema(
        operation_description="Get notable drops",
        responses={200: NotableDropSerializer, 404: "no drops found"},
    )
    def get(self, request):
        drops = NotableDrop.objects.all()
        if not drops:
            return Response("no drops found", status=status.HTTP_404_NOT_FOUND)
        response_data = NotableDropSerializer(drops, many=True).data
        return Response(response_data, status=status.HTTP_200_OK)
