import random
from decimal import Decimal
from datetime import timedelta

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
    Ownership, 
    Status, 
    Tags, 
    Token,
    TransactionTracker,
)
from src.store.serializers import (
    BetSerializer, 
    BidSerializer,
   CollectionMetadataSerializer,
   CollectionSerializer,
   CollectionSlimSerializer,
   HotCollectionSerializer,
   TokenFullSerializer, TokenPatchSerializer,
   TokenSerializer,
)
from src.store.services.ipfs import create_ipfs, send_to_ipfs
from src.utilities import get_page_slice, sign_message
from django.core.exceptions import ObjectDoesNotExist
from django.core.mail import send_mail
from django.db.models import Count, Q, Sum
from django.utils import timezone
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import (
    IsAuthenticated,
    IsAuthenticatedOrReadOnly,
)
from rest_framework.response import Response
from rest_framework.views import APIView


transfer_tx = openapi.Response(
    description='Response with prepared transfer tx',
    schema=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'tx': openapi.Schema(type=openapi.TYPE_STRING),
        }
    )
)


create_response = openapi.Response(
    description='Response with created token',
    schema=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'id': openapi.Schema(type=openapi.TYPE_NUMBER),
            'total_supply': openapi.Schema(type=openapi.TYPE_NUMBER),
            'available': openapi.Schema(type=openapi.TYPE_NUMBER),
            'price': openapi.Schema(type=openapi.TYPE_NUMBER),
            'USD_price': openapi.Schema(type=openapi.TYPE_NUMBER),
            'owner': openapi.Schema(type=openapi.TYPE_STRING),
            'creator': openapi.Schema(type=openapi.TYPE_STRING),
            'collection': openapi.Schema(type=openapi.TYPE_STRING),
            'standart': openapi.Schema(type=openapi.TYPE_STRING),
            'details': openapi.Schema(type=openapi.TYPE_OBJECT),
        }
    )
)

buy_token_response = openapi.Response(
    description='Response with buyed token',
    schema=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'initial_tx': openapi.Schema(type=openapi.TYPE_OBJECT),
            'nonce': openapi.Schema(type=openapi.TYPE_NUMBER),
            'gasPrice': openapi.Schema(type=openapi.TYPE_NUMBER),
            'gas': openapi.Schema(type=openapi.TYPE_NUMBER),
            'to': openapi.Schema(type=openapi.TYPE_STRING),
            'value': openapi.Schema(type=openapi.TYPE_NUMBER),
            'data': openapi.Schema(type=openapi.TYPE_OBJECT),
            'id_order': openapi.Schema(type=openapi.TYPE_STRING),
            'whoIsSelling': openapi.Schema(type=openapi.TYPE_STRING),
            'tokenToBuy': openapi.Schema(type=openapi.TYPE_OBJECT),
            'tokenAddress': openapi.Schema(type=openapi.TYPE_STRING),
            'id': openapi.Schema(type=openapi.TYPE_NUMBER),
            'amount': openapi.Schema(type=openapi.TYPE_NUMBER),
            'tokenToSell': openapi.Schema(type=openapi.TYPE_OBJECT),
            'tokenAddress': openapi.Schema(type=openapi.TYPE_STRING),
            'id': openapi.Schema(type=openapi.TYPE_NUMBER),
            'feeAddresses': openapi.Schema(type=openapi.TYPE_ARRAY, items=openapi.Items(type=openapi.TYPE_STRING)),
            'feeAmount': openapi.Schema(type=openapi.TYPE_ARRAY, items=openapi.Items(type=openapi.TYPE_NUMBER)),
            'signature': openapi.Schema(type=openapi.TYPE_STRING),
        }
    )
)

not_found_response = 'user not found'

class SearchView(APIView):
    '''
    View for search items in shop.
    searching has simple 'contains' logic.
    '''
    @swagger_auto_schema(
        operation_description="post search pattern",
        manual_parameters=[
            openapi.Parameter(
                "sort",
                openapi.IN_QUERY,
                type=openapi.TYPE_STRING,
                description="Search by: items, users, collections",
            ),
            # openapi.Parameter("tags", openapi.IN_QUERY, type=openapi.TYPE_ARRAY),
            openapi.Parameter("is_verified", openapi.IN_QUERY, type=openapi.TYPE_BOOLEAN),
            openapi.Parameter("max_price", openapi.IN_QUERY, type=openapi.TYPE_NUMBER),
            openapi.Parameter(
                "order_by",
                openapi.IN_QUERY,
                type=openapi.TYPE_STRING,
                description="For tokens: date, price, likes. \n For users: created, followers, tokens_created",
            ),
            openapi.Parameter("on_sale", openapi.IN_QUERY, type=openapi.TYPE_BOOLEAN),
            openapi.Parameter("currency", openapi.IN_QUERY, type=openapi.TYPE_STRING),
            openapi.Parameter("page", openapi.IN_QUERY, type=openapi.TYPE_NUMBER),
            openapi.Parameter("network", openapi.IN_QUERY, type=openapi.TYPE_STRING),
            openapi.Parameter("creator", openapi.IN_QUERY, type=openapi.TYPE_STRING),
            openapi.Parameter("owner", openapi.IN_QUERY, type=openapi.TYPE_STRING),
        ],
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            manual_parameters=[
                openapi.Parameter(
                    "sort", 
                    openapi.IN_QUERY, 
                    type=openapi.TYPE_STRING, 
                    description="Search by: items, users, collections",
                ),
                # openapi.Parameter("tags", openapi.IN_QUERY, type=openapi.TYPE_ARRAY),
                openapi.Parameter("is_verified", openapi.IN_QUERY, type=openapi.TYPE_BOOLEAN),
                openapi.Parameter("max_price", openapi.IN_QUERY, type=openapi.TYPE_NUMBER),
                openapi.Parameter(
                    "order_by", 
                    openapi.IN_QUERY, 
                    type=openapi.TYPE_STRING,
                    description="For tokens: date, price, likes. \n For users: created, followers, tokens_created",
                ),
                openapi.Parameter("on_sale", openapi.IN_QUERY, type=openapi.TYPE_BOOLEAN),
                openapi.Parameter("currency", openapi.IN_QUERY, type=openapi.TYPE_STRING),
                openapi.Parameter("page", openapi.IN_QUERY, type=openapi.TYPE_NUMBER),
                openapi.Parameter("network", openapi.IN_QUERY, type=openapi.TYPE_STRING),
                openapi.Parameter("creator", openapi.IN_QUERY, type=openapi.TYPE_STRING),
                openapi.Parameter("owner", openapi.IN_QUERY, type=openapi.TYPE_STRING),
            ],
            properties={
                'text': openapi.Schema(type=openapi.TYPE_STRING),
                'page': openapi.Schema(type=openapi.TYPE_NUMBER)
            }
        ),
        responses={200: TokenSerializer(many=True)},
    )
    def post(self, request):
        request_data = request.data
        words = request_data.get('text', '')
        params = request.query_params
        sort = params.get('type', 'items')

        sort_type = getattr(config.SEARCH_TYPES, sort)
        token_count, search_result = getattr(Search(), f"{sort_type}_search")(
            words=words, 
            user=request.user, 
            **params,
        )
        response_data = {"total_tokens": token_count, "items": search_result}

        return Response(response_data, status=status.HTTP_200_OK)


class CreateView(APIView):
    '''
    View for create token transaction.
    '''
    permission_classes = [IsAuthenticated]
    @swagger_auto_schema(
        operation_description="token_creation",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'name': openapi.Schema(type=openapi.TYPE_STRING),
                'standart': openapi.Schema(type=openapi.TYPE_STRING),
                'total_supply': openapi.Schema(type=openapi.TYPE_NUMBER),
                'currency': openapi.Schema(type=openapi.TYPE_STRING),
                'description': openapi.Schema(type=openapi.TYPE_STRING),
                'price': openapi.Schema(type=openapi.TYPE_NUMBER),
                'minimal_bid': openapi.Schema(type=openapi.TYPE_NUMBER),
                'creator_royalty': openapi.Schema(type=openapi.TYPE_NUMBER),
                'collection': openapi.Schema(type=openapi.TYPE_NUMBER),
                'details': openapi.Schema(type=openapi.TYPE_OBJECT),
                'selling': openapi.Schema(type=openapi.TYPE_STRING),
                'start_auction': openapi.Schema(type=openapi.FORMAT_DATETIME),
                'end_auction': openapi.Schema(type=openapi.FORMAT_DATETIME),
                'digital_key': openapi.Schema(type=openapi.TYPE_STRING),
                
                'media': openapi.Schema(type=openapi.TYPE_STRING, format=openapi.FORMAT_BINARY),
                'cover': openapi.Schema(type=openapi.TYPE_STRING, format=openapi.FORMAT_BINARY),
                'format': openapi.Schema(type=openapi.TYPE_STRING),
            }),
        responses={200: create_response},
    )
    def post(self, request):
        request_data = request.data
        standart = request_data.get('standart')
        creator = request.user
        token_collection_id = request_data.get('collection')
        
        try:
            token_collection = Collection.objects.committed().get_by_short_url(token_collection_id)
        except:
            return Response({'error': 'Collection not found'}, status=status.HTTP_400_BAD_REQUEST)

        if standart != token_collection.standart:
            return Response({'standart': 'collections type mismatch'}, status=status.HTTP_400_BAD_REQUEST)

        if Token.objects.filter(name=request_data.get('name')):
            return Response({'name': 'name already used'}, status=status.HTTP_400_BAD_REQUEST)

        ipfs = create_ipfs(request)
        if standart == 'ERC721':
            signature = sign_message(
                ['address', 'string'],
                [token_collection.network.wrap_in_checksum(token_collection.ethereum_address), ipfs]
            )
            amount = 1
        else:
            amount = request_data.get('total_supply')
            signature = sign_message(
                ['address', 'string', 'uint256'],
                [token_collection.network.wrap_in_checksum(token_collection.ethereum_address), ipfs, int(amount)]
            )

        initial_tx = token_collection.create_token(creator, ipfs, signature, amount)
        token = Token()
        token.save_in_db(request, ipfs)
        response_data = {'initial_tx': initial_tx, 'token': TokenSerializer(token).data}
        return Response(response_data, status=status.HTTP_200_OK)


class CreateCollectionView(APIView):
    '''
    View for create collection transaction..
    '''
    permission_classes = [IsAuthenticated]
    @swagger_auto_schema(
        operation_description="collection_creation",
        manual_parameters=[
            openapi.Parameter("network", openapi.IN_QUERY, type=openapi.TYPE_STRING),
        ],
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'name': openapi.Schema(type=openapi.TYPE_STRING),
                'standart': openapi.Schema(type=openapi.TYPE_STRING),
                'avatar': openapi.Schema(type=openapi.TYPE_STRING, format=openapi.FORMAT_BINARY),
                'symbol': openapi.Schema(type=openapi.TYPE_STRING),
                'description': openapi.Schema(type=openapi.TYPE_STRING),
                'short_url': openapi.Schema(type=openapi.TYPE_STRING),
            },
            required=['name', 'creator', 'avatar', 'symbol', 'standart'],
        ),
    )
    def post(self, request):
        name = request.data.get('name')
        symbol = request.data.get('symbol')
        short_url = request.data.get('short_url')
        standart = request.data.get('standart')
        network = request.query_params.get('network', config.DEFAULT_NETWORK)
        print(network)
        owner = request.user

        is_unique, response = Collection.collection_is_unique(name, symbol, short_url, network)
        if not is_unique:
            return response

        if standart not in ["ERC721", "ERC1155"]:
            return Response('invalid collection type', status=status.HTTP_400_BAD_REQUEST)
        
        network = Network.objects.filter(name__icontains=network)
        print(network.first().name)
        if not network:
            return Response('invalid network name', status=status.HTTP_400_BAD_REQUEST)

        initial_tx = Collection.create_contract(name, symbol, standart, owner, network.first())

        collection = Collection()

        media = request.FILES.get('avatar')
        print(media)
        if media:
            ipfs = send_to_ipfs(media)
        else:
            ipfs = None
        print(ipfs)
        collection.save_in_db(request, ipfs)
        response_data = {'initial_tx': initial_tx, 'collection': CollectionSlimSerializer(collection).data}
        return Response(response_data, status=status.HTTP_200_OK)


class GetLikedView(APIView):
    '''
    View for getting all items liked by address
    '''
    @swagger_auto_schema(
        operation_description="get tokens liked by address",
        responses={200: TokenSerializer(many=True), 401: not_found_response},
        manual_parameters=[
            openapi.Parameter("network", openapi.IN_QUERY, type=openapi.TYPE_STRING),
        ],
    )

    def get(self, request, user_id, page):
        network = request.query_params.get('network', config.DEFAULT_NETWORK)
        try:
            user = AdvUser.objects.get_by_custom_url(user_id)
        except ObjectDoesNotExist:
            return Response({'error': not_found_response}, status=status.HTTP_401_UNAUTHORIZED)

        # get users associated with the model UserAction
        ids = user.followers.all().values_list('user')
        
        # get tokens that users like
        tokens_action = UserAction.objects.filter(method='like', user__in=ids).order_by('-date')
        
        tokens = [action.token for action in tokens_action]
        if network:
            tokens = [token for token in tokens if network.lower() in token.collection.network.name.lower()]

        start, end = get_page_slice(page, len(tokens))
        token_list = tokens[start:end]
        response_data = TokenSerializer(token_list, many=True, context={"user": request.user}).data
        return Response(response_data, status=status.HTTP_200_OK)


class GetView(APIView):
    '''
    View for get token info.
    '''
    permission_classes = [IsAuthenticatedOrReadOnly]
    @swagger_auto_schema(
        operation_description="get token info",
        responses={200: TokenFullSerializer, 401: not_found_response},
    )
    def get(self, request, id):
        try:
            token = Token.objects.committed().get(id=id)
        except ObjectDoesNotExist:
            return Response('token not found', status=status.HTTP_401_UNAUTHORIZED)
        response_data = TokenFullSerializer(token, context={"user": request.user}).data
        return Response(response_data, status=status.HTTP_200_OK)

    @swagger_auto_schema(
        operation_description="update owned token info",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'selling': openapi.Schema(type=openapi.TYPE_BOOLEAN),
                'minimal_bid': openapi.Schema(type=openapi.TYPE_NUMBER),
                'price': openapi.Schema(type=openapi.TYPE_NUMBER),
                'currency': openapi.Schema(type=openapi.TYPE_STRING),
                'start_auction': openapi.Schema(type=openapi.FORMAT_DATETIME),
                'end_auction': openapi.Schema(type=openapi.FORMAT_DATETIME),
            },
        ),
        responses={200: TokenFullSerializer, 401: not_found_response, 400: "this token doesn't belong to you"},
    )
    def patch(self, request, id):
        request_data = request.data.copy()
        user = request.user

        try:
            token = Token.objects.committed().get(id=id)
        except ObjectDoesNotExist:
            return Response({'error': not_found_response}, status=status.HTTP_404_NOT_FOUND)
        
        is_valid, response = token.is_valid(user)
        if not is_valid:
            return response
        price = request_data.get('price', None)
        print(f'price is {price}')
        minimal_bid = request_data.get('minimal_bid', None)
        start_auction = request_data.get('start_auction')
        end_auction = request_data.get('end_auction')
        selling = request_data.get('selling')
        if price:
            request_data.pop('price', None)
            price = Decimal(str(price))
        request_data['currency_price'] = price 
        if minimal_bid:
            request_data.pop('minimal_bid')
            minimal_bid = Decimal(str(minimal_bid))
        request_data['currency_minimal_bid'] = minimal_bid
        
        if token.standart == "ERC721":
            old_price = token.currency_price
            amount = 1

            request_data['start_auction'] = start_auction
            request_data['end_auction'] = end_auction
            serializer = TokenPatchSerializer(token, data=request_data, partial=True)

            print(f"PatchSerializer valid - {serializer.is_valid()}")
            if serializer.is_valid():
                serializer.save()
        else:
            ownership = Ownership.objects.get(owner=user, token=token)
            old_price = ownership.currency_price
            amount = ownership.quantity
            ownership.selling = selling
            ownership.currency_price = price
            ownership.currency_minimal_bid = minimal_bid
            ownership.full_clean()
            ownership.save()

        # add changes to listing
        if price != old_price:
            TokenHistory.objects.create(
                token=token,
                old_owner=user,
                amount=amount,
                price=price,
                method='Listing',
            )

        response_data = TokenFullSerializer(token, context={"user": request.user}).data
        return Response(response_data, status=status.HTTP_200_OK)


class TokenBurnView(APIView):
    '''
    View for burn token.
    '''
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="token burn",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'amount': openapi.Schema(type=openapi.TYPE_NUMBER),
            }),
        responses={200: transfer_tx},
    )
    def post(self, request, token_id):
        user = request.user
        token = Token.objects.committed().get(id=token_id)
        amount = request.data.get("amount")
        is_valid, res = token.is_valid(user=user)
        if not is_valid:
            return res
        return Response({'initial_tx': token.burn(user, amount)}, status=status.HTTP_200_OK)


class GetHotView(APIView):
    '''
    View for getting hot items
    '''

    @swagger_auto_schema(
        operation_description="get hot tokens",
        responses={200: TokenFullSerializer(many=True)},
        manual_parameters=[
            openapi.Parameter('sort', openapi.IN_QUERY, type=openapi.TYPE_STRING),
            openapi.Parameter('tag', openapi.IN_QUERY, type=openapi.TYPE_STRING),
            openapi.Parameter('network', openapi.IN_QUERY, type=openapi.TYPE_STRING),
        ],
    )
    def get(self, request, page):
        sort = request.query_params.get('sort', 'recent')
        tag = request.query_params.get('tag')
        network = request.query_params.get('network', config.DEFAULT_NETWORK)
        order = getattr(config.SORT_STATUSES, sort)
        tokens = Token.objects.committed().network(network)
        if tag:
            tokens = tokens.filter(tags__name__contains=tag).order_by(order)
        else:
            tokens = tokens.order_by(order)
        if sort in ('cheapest', 'highest'):
            tokens = tokens.exclude(price=None).exclude(selling=False)
        length = tokens.count()

        start, end = get_page_slice(page, len(tokens))

        token_list = tokens[start:end]
        response_data = TokenFullSerializer(token_list, context={"user": request.user}, many=True).data
        return Response({'tokens': response_data, 'length': length}, status=status.HTTP_200_OK)


class GetHotCollectionsView(APIView):
    '''
    View for getting hot collections
    '''

    @swagger_auto_schema(
        operation_description="get hot collections",
        manual_parameters=[
            openapi.Parameter('network', openapi.IN_QUERY, type=openapi.TYPE_STRING),
        ],
        responses={200: HotCollectionSerializer(many=True)},
    )
    def get(self, request):
        network = request.query_params.get('network', config.DEFAULT_NETWORK)
        collections = Collection.objects.committed().hot_collections(network).order_by('-id')[:5]
        response_data = HotCollectionSerializer(collections, many=True).data
        return Response(response_data, status=status.HTTP_200_OK)


class GetCollectionView(APIView):
    '''
    View for get collection info in shop.
    '''
    @swagger_auto_schema(
        operation_description="get collection info",
        manual_parameters=[
            openapi.Parameter('network', openapi.IN_QUERY, type=openapi.TYPE_STRING),
            openapi.Parameter('page', openapi.IN_QUERY, type=openapi.TYPE_NUMBER),
        ],
        responses={200: CollectionSerializer, 400: 'collection not found'},
    )

    def get(self, request, param):
        page = request.query_params.get('page', 1)
        try:
            collection = Collection.objects.committed().get_by_short_url(param)
        except ObjectDoesNotExist:
            return Response({'error': 'collection not found'}, status=status.HTTP_400_BAD_REQUEST)

        attribute_dict = dict(request.query_params)
        attribute_dict.pop('network')
        '''
        Creating a dict of token attributes from query parameters in url, i.e.:
        {hair: [black, red, blone]
        eyes: [red, blue, brown]
        height: [tall, short]}
        '''
        tokens = Token.objects.committed().filter(collection=collection)
        if attribute_dict:
            #iterating through both atributes and values in a dict to dynamically 
            #filter tokens with required attribute values in their details
            for attribute_ , value in attribute_dict.items():
                attribute_filter = {f"details__{attribute_}__in": value}
                tokens = tokens.filter(**attribute_filter)

        # Serializing the list of filtered tokens
        start, end = get_page_slice(page, len(tokens), items_per_page=5)
        tokens_count = len(tokens)
        response_data = CollectionSerializer(collection, context={"tokens": tokens[start:end], "tokens_count": tokens_count}).data
        return Response(response_data, status=status.HTTP_200_OK)


class TransferOwned(APIView):
    '''
    View for tansfering token owned by user.
    '''
    permission_classes = [IsAuthenticated]
    @swagger_auto_schema(
        operation_description="transfer_owned",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'address': openapi.Schema(type=openapi.TYPE_STRING),
                'amount': openapi.Schema(type=openapi.TYPE_NUMBER)
            }),
        responses={200: transfer_tx, 400: "you can not transfer tokens that don't belong to you"},
    )
    def post(self, request, token):
        address = request.data.get("address")
        amount = request.data.get("amount")
        user = request.user
        transferring_token = Token.objects.get(id=token)

        is_valid, response = transferring_token.is_valid(user=user)
        if not is_valid:
            return response

        initial_tx = transferring_token.transfer(user, address, amount)
        return Response({"initial_tx": initial_tx}, status=status.HTTP_200_OK)


class BuyTokenView(APIView):
    '''
    view to buy a token
    '''
    permission_classes = [IsAuthenticated]
    @swagger_auto_schema(
        operation_description="buy_token",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'id': openapi.Schema(type=openapi.TYPE_NUMBER),
                'tokenAmount': openapi.Schema(type=openapi.TYPE_NUMBER),
                'sellerId': openapi.Schema(type=openapi.TYPE_STRING),
            }),
        responses={200:buy_token_response, 400:"you cant buy token"}
    )
    def post(self, request):
        buyer = request.user
        seller_id = request.data.get('sellerId')
        token_id = request.data.get('id')
        token_amount = request.data.get('tokenAmount')

        if token_id is None:
            return Response({"error": "invalid token_id"}, status=status.HTTP_400_BAD_REQUEST)
        if token_amount is None:
            return Response({"error": "invalid token_amount"}, status=status.HTTP_400_BAD_REQUEST)

        token_id = int(token_id)
        token_amount = int(token_amount)
        tradable_token = Token.objects.get(id=token_id)

        is_valid, response = tradable_token.is_valid_for_buy(token_amount, seller_id)
        if not is_valid:
            return response

        buyer = request.user
        try:
            if seller_id:
                seller = AdvUser.objects.get_by_custom_url(seller_id)
                ownership = Ownership.objects.filter(token__id=token_id, owner=seller).filter(selling=True)
                if not ownership:
                    return Response({'error': 'user is not owner or token is not on sell'})
            else:
                seller = None
        except ObjectDoesNotExist:
            return Response({'error': 'user not found'}, status=status.HTTP_400_BAD_REQUEST)

        buy = tradable_token.buy_token(token_amount, buyer, seller)
        return Response({'initial_tx': buy}, status=status.HTTP_200_OK)


@api_view(http_method_names=['GET'])
def get_tags(request):
    tag_list = [{"title": tag.name, "icon": tag.ipfs_icon} for tag in Tags.objects.all()]
    return Response({'tags': tag_list}, status=status.HTTP_200_OK)


class MakeBid(APIView):
    '''
    view for making bid on auction
    '''
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="make_bid",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'token_id': openapi.Schema(type=openapi.TYPE_NUMBER),
                'amount': openapi.Schema(type=openapi.TYPE_NUMBER),
                'quantity': openapi.Schema(type=openapi.TYPE_NUMBER)
            }),
        responses={400:"you cant buy token"}
    )

    def post(self, request):
        request_data = request.data
        token_id = request_data.get('token_id')
        amount = Decimal(str(request_data.get('amount')))
        quantity = int(request_data.get('quantity'))
        token = Token.objects.get(id=token_id)
        user = request.user

        if token.currency.address == "0xEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEE":
            return Response(
                {'error': 'You cannot bet on native currencies'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        #returns OK if valid, or error message
        result = validate_bid(user, token_id, amount, quantity)

        if result != 'OK':
            return Response({'error': result}, status=status.HTTP_400_BAD_REQUEST)

        #create new bid or update old one
        bid, created = Bid.objects.get_or_create(user=user, token=Token.objects.get(id=token_id))

        if not created and bid.amount >= amount:
            return Response({'error': 'you cannot lower your bid'}, status=status.HTTP_400_BAD_REQUEST)

        bid.amount = amount
        bid.quantity = quantity
        bid.full_clean()
        bid.save()


        #construct approve tx if not approved yet:
        allowance = bid.token.currency.network.contract_call(
            method_type='read',
            contract_type='token',
            address=token.currency.address,
            function_name='allowance',
            input_params=(
                user.username,
                bid.token.currency.network.exchange_address
            ),
            input_type=('address', 'address'),
            output_types=('uint256',),
        )

        user_balance = bid.token.currency.network.contract_call(
            method_type='read', 
            contract_type='token',
            address=token.currency.address, 
            function_name='balanceOf',
            input_params=(user.username,),
            input_type=('address',),
            output_types=('uint256',),
        )



        amount, _ = calculate_amount(amount, bid.token.currency.symbol)

        if allowance < amount * quantity:

            initial_tx = bid.token.collection.network.contract_call(
                method_type = 'write',
                contract_type='token',
                address=token.currency.address,

                gas_limit = APPROVE_GAS_LIMIT,
                nonce_username = user.username,
                tx_value = None,

                function_name= 'approve',
                input_params=(
                    bid.token.collection.network.wrap_in_checksum(token.collection.network.exchange_address),
                    user_balance,
                ),
                input_type=('address', 'uint256')
            )

            return Response({'initial_tx': initial_tx}, status=status.HTTP_200_OK)

        bid.state = Status.COMMITTED
        bid.full_clean()
        bid.save()

        BidsHistory.objects.create(
            token=bid.token,
            user=bid.user,
            price=bid.amount,
            date=bid.created_at,
        )

        return Response({'bid created, allowance not needed'}, status=status.HTTP_200_OK)


@api_view(http_method_names=['GET'])
@permission_classes([IsAuthenticated])
def get_bids(request, token_id):
    #validating token and user
    try:
        token = Token.objects.committed().get(id=token_id)
    except ObjectDoesNotExist:
        return Response({'error': 'token not found'}, status=status.HTTP_400_BAD_REQUEST)
    if token.is_auc_selling:
        return Response({'error': 'token is not set on auction'}, status=status.HTTP_400_BAD_REQUEST)
    user = request.user
    if token.owner != user:
        return Response({'error': 'you can get bids list only for owned tokens'}, status=status.HTTP_400_BAD_REQUEST)

    bids = Bid.objects.filter(token=token)
    response_data = BidSerializer(bids, many=True).data
    return Response(response_data, status=status.HTTP_200_OK)


class VerificateBetView(APIView):

    @swagger_auto_schema(
        operation_description="verificate bet",
        responses={200: BetSerializer, 400: 'verificate bet not found'},
    )
    def get(self, request, token_id):
        print('virificate!')
        token = Token.objects.get(id=token_id)
        bets = Bid.objects.filter(token=token).order_by('-amount')
        max_bet = bets.first()
        if not max_bet:
            return Response(
                    {'invalid_bet': None, 'valid_bet': None},
                    status=status.HTTP_200_OK)
            
        user = max_bet.user
        amount = max_bet.amount
        quantity = max_bet.quantity

        check_valid = validate_bid(user, token_id, amount, quantity)

        if check_valid == 'OK':
            print('all ok!')
            return Response(BetSerializer(max_bet).data, status=status.HTTP_200_OK)
        else:
            print('not ok(')
            max_bet.delete()
            print(bets)
            for bet in bets:
                user = bet.user
                amount = bet.amount
                quantity = bet.quantity
                check_valid = validate_bid(user, token_id, amount, quantity)
                if check_valid == 'OK':
                    print('again ok!')
                    return Response(
                        {
                            'invalid_bet': BetSerializer(max_bet).data,
                            'valid_bet': BetSerializer(bet).data,
                        }, 
                        status=status.HTTP_200_OK
                    )
                else:
                    bet.delete()
                    continue
            return Response(
                {'invalid_bet': BetSerializer(max_bet).data, 'valid_bet': None},
                status=status.HTTP_200_OK)


class AuctionEndView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description='end if auction and take the greatest bet',
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'token': openapi.Schema(type=openapi.TYPE_STRING)
            }),
        responses={200:buy_token_response, 400: 'cant sell token'}
    )
    def post(self, request, token_id):

        bet = Bid.objects.filter(token__id=token_id).order_by('-amount').first()
        if not bet:
            return {'error': 'no active bids'}

        token = bet.token
        buyer = bet.user
        price = bet.amount * bet.token.currency.get_decimals

        seller = request.user
        if token.standart == 'ERC721':
            if seller != token.owner:
                return Response({'error': 'user is not owner or token is not on sell'})
        else:
            ownership = Ownership.objects.filter(
                token=token, 
                owner=seller, 
                selling=True, 
                currency_minimal_bid__isnull=False,
            ).first()
            if not ownership:
                return Response({'error': 'user is not owner or token is not on sell'})

        if token.standart == 'ERC721':
            token_amount = 0
        else:
            token_amount = min(bet.quantity, ownership.quantity)

        sell = token.buy_token(token_amount, buyer,seller=seller, price=price, auc=True)
        return Response({'initial_tx': sell}, status=status.HTTP_200_OK)


class ReportView(APIView):

    @swagger_auto_schema(
        operation_description='report page',
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'page': openapi.Schema(type=openapi.TYPE_STRING),
                'message': openapi.Schema(type=openapi.TYPE_STRING),
                'token': openapi.Schema(type=openapi.TYPE_STRING)
            }
        ),
        responses={200: 'your report sent to admin', 400: 'report not sent to admin'}
    )
    def post(self, request):
        '''
        view for report form
        '''
        request_data = request.data
        page = request_data.get('page')
        message = request_data.get('message')
        response = request_data.get('token')

        if config.CAPTCHA_SECRET:
            if not check_captcha(response):
                return Response('you are robot. go away, robot!', status=status.HTTP_400_BAD_REQUEST)

        connection = get_email_connection()
        text = """
                Page: {page}
                Message: {message}
                """.format(page=page, message=message)

        send_mail(
            'Report from digital dollar store',
            text,
            config.HOST_USER,
            [config.MAIL],
            connection=connection,
        )
        print('message sent')

        return Response('OK', status=status.HTTP_200_OK)


class SetCoverView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description='set cover',
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'id': openapi.Schema(type=openapi.TYPE_NUMBER),
                'cover': openapi.Schema(type=openapi.TYPE_STRING, format=openapi.FORMAT_BINARY)
            }
        ),
        responses={200: 'OK', 400: 'error'}
    )
    def post(self, request):
        user = request.user
        collection_id = request.data.get('id')
        try:
            collection = Collection.objects.committed().get_by_short_url(collection_id)
        except ObjectDoesNotExist:
            return Response({'error': 'collection not found'}, status=status.HTTP_400_BAD_REQUEST)
        if collection.creator != user:
            return Response({'error': 'you can set covers only for your collections'}, status=status.HTTP_400_BAD_REQUEST)
        media = request.FILES.get('cover')
        if media:
            ipfs = send_to_ipfs(media)
            collection.cover_ipfs = ipfs
            collection.save()
        return Response(collection.cover, status=status.HTTP_200_OK)


@api_view(http_method_names=['GET'])
def get_fee(request):
    currency_symbol = request.query_params.get('currency')
    currency = UsdRate.objects.get(symbol=currency_symbol)
    return Response(currency.service_fee, status=status.HTTP_200_OK)


@swagger_auto_schema(
    methods=['get'], 
    manual_parameters=[openapi.Parameter("network", openapi.IN_QUERY, type=openapi.TYPE_STRING),], 
    responses={200: TokenSerializer, 404: "Token not found"},
)
@api_view(http_method_names=['GET'])
def get_random_token(request):
    network = request.query_params.get('network', config.DEFAULT_NETWORK)
    token_list = Token.objects.committed().network(network).filter(
        Q(owner__is_verificated=True) | Q(owners__is_verificated=True)
    )
    if not token_list.exists():
        return Response("Token not found", status=status.HTTP_404_NOT_FOUND)
    token = random.choice(token_list)
    response_data = TokenSerializer(token).data
    return Response(response_data, status=status.HTTP_200_OK)


@api_view(http_method_names=['GET'])
def get_favorites(request):
    network = request.query_params.get('network', config.DEFAULT_NETWORK)
    token_list = Token.objects.committed().network(network).filter(is_favorite=True).order_by("-updated_at")
    tokens = TokenFullSerializer(token_list, many=True, context={"user": request.user}).data
    response_data = [token for token in tokens if token.get("available")]
    return Response(response_data, status=status.HTTP_200_OK)


@api_view(http_method_names=['GET'])
def get_hot_bids(request):
    network = request.query_params.get('network', config.DEFAULT_NETWORK)
    bids = Bid.objects.filter(state=Status.COMMITTED).filter(
        token__collection__network__name__icontains=network
        ).distinct('token')[:6]
    token_list = [bid.token for bid in bids]
    response_data = TokenFullSerializer(token_list, context={"user": request.user}, many=True).data
    return Response(response_data, status=status.HTTP_200_OK)


class SupportView(APIView):

    @swagger_auto_schema(
        operation_description='support view',
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'email': openapi.Schema(type=openapi.TYPE_STRING),
                'message': openapi.Schema(type=openapi.TYPE_STRING),
                'token': openapi.Schema(type=openapi.TYPE_STRING)
            }
        ),
        responses={200: 'your report sent to admin', 400: 'report not sent to admin'}
    )
    def post(self, request):
        '''
        view for report form
        '''
        request_data = request.data
        email = request_data.get('email')
        message = request_data.get('message')
        response = request_data.get('token')

        if config.CAPTCHA_SECRET:
            if not check_captcha(response):
                return Response('you are robot. go away, robot!', status=status.HTTP_400_BAD_REQUEST)

        connection = get_email_connection()
        text = """
                Email: {email}
                Message: {message}
                """.format(email=email, message=message)

        send_mail(
            'Support form from digital dollar store',
            text,
            config.HOST_USER,
            [config.MAIL],
            connection=connection,
        )
        print('message sent')

        return Response('OK', status=status.HTTP_200_OK)


class TransactionTrackerView(APIView):
    """
    View for transaction tracking
    """
    @swagger_auto_schema(
        operation_description="transaction_tracker",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'tx_hash': openapi.Schema(type=openapi.TYPE_STRING),
                'token': openapi.Schema(type=openapi.TYPE_NUMBER),
                'ownership': openapi.Schema(type=openapi.TYPE_STRING),
                'amount': openapi.Schema(type=openapi.TYPE_NUMBER),
            }),
    )
    def post(self, request):
        token_id = request.data.get("token")
        tx_hash = request.data.get("tx_hash")
        amount = request.data.get("amount")

        token = Token.objects.filter(id=token_id).first()

        if not token:
            return Response({"error": "token not found"}, status=status.HTTP_400_BAD_REQUEST)

        if token.standart == "ERC1155":
            owner_url = request.data.get("ownership")
            user = AdvUser.objects.get_by_custom_url(owner_url)
            ownership = Ownership.objects.filter(token_id=token_id, owner=user).first()
            owner_amount = TransactionTracker.objects.aggregate(total_amount=Sum('amount'))
            owner_amount = owner_amount['total_amount'] or 0
            if owner_amount and ownership.quantity <= owner_amount + int(amount):
                ownership.selling = False
                ownership.save()
            TransactionTracker.objects.create(token=token, ownership=ownership, tx_hash=tx_hash, amount=amount)
            return Response({"success": "trancsaction is tracked"}, status=status.HTTP_200_OK)
        token.selling = False
        token.save()
        TransactionTracker.objects.create(token=token, tx_hash=tx_hash)
        return Response({"success": "trancsaction is tracked"}, status=status.HTTP_200_OK)


class GetCollectionByAdressView(APIView):
    '''
    View for get collection metadata by adress.
    '''
    @swagger_auto_schema(
        operation_description="get collection metadata by adress",
        responses={200: CollectionMetadataSerializer, 400: 'collection not found'},
    )

    def get(self, request, address):
        try:
            collection = Collection.objects.committed().get(address__iexact=address)
        except ObjectDoesNotExist:
            return Response({'error': 'collection not found'}, status=status.HTTP_400_BAD_REQUEST)

        response_data = CollectionMetadataSerializer(collection).data
        return Response(response_data, status=status.HTTP_200_OK)


def get_token_max_price(token):
    if not (token.is_selling or token.is_auc_selling):
        return 0
    if token.standart=="ERC721":
        return token.currency_price if token.currency_price else token.currency_minimal_bid
    owners = token.ownership_set.all()
    prices = [owner.currency_price if owner.currency_price else owner.currency_minimal_bid for owner in owners if owner.selling]
    return max(prices)


@api_view(http_method_names=['GET'])
def get_max_price(request):
    network = request.query_params.get('network', config.DEFAULT_NETWORK)
    currency = request.query_params.get('currency')
    tokens = Token.objects.committed().network(network).filter(currency__symbol=currency)
    token_prices = [get_token_max_price(t) for t in tokens]
    max_price = 100
    if token_prices:
        max_price = max(token_prices)
    return Response({'max_price': max_price}, status=status.HTTP_200_OK)


class GetMostBiddedView(APIView):
    '''
    View for get info for token with most bid count.
    '''
    #permission_classes = [IsAuthenticatedOrReadOnly]
    @swagger_auto_schema(
        operation_description="get hot auction",
        responses={200: TokenFullSerializer, 401: not_found_response},
    )

    def get(self, request):
        tokens = Token.objects.committed().annotate(bid_count=Count('bid')).filter(bid_count__gt=0).order_by('-bid_count')[:5]
        if not tokens:
            return Response('token not found', status=status.HTTP_404_NOT_FOUND)
        response_data = TokenFullSerializer(tokens, many=True, context={"user": request.user}).data
        return Response(response_data, status=status.HTTP_200_OK)


class GetRelatedView(APIView):
    '''
    View for get info for token related to id.
    '''
    permission_classes = [IsAuthenticatedOrReadOnly]

    @swagger_auto_schema(
        operation_description="get related",
        responses={200: TokenSerializer, 401: not_found_response},
    )
    def get(self, request, id):
        try:
            token = Token.objects.committed().get(id=id)

        except ObjectDoesNotExist:
            return Response('token not found', status=status.HTTP_401_UNAUTHORIZED)
        all_related = Token.objects.committed().filter(collection=token.collection)
        random_related = random.choices(all_related, k=4)
        response_data = TokenSerializer(random_related, many=True, context={"user": request.user}).data
        return Response(response_data, status=status.HTTP_200_OK)


class RemoveRejectView(APIView):
    '''
    View for remove rejected token or collection by id.
    '''
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Remove rejected token or collection",
        request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
            properties={
            'id': openapi.Schema(type=openapi.TYPE_NUMBER),
            'type': openapi.Schema(type=openapi.TYPE_STRING),
        }),
        responses={200: "success"},
    )
    def post(self, request):
        items = {
            'token': Token,
            'collection': Collection,
        }
        item_id = request.data.get("id")
        item_type = request.data.get("type")
        if item_type not in ['token', 'collection']:
            return Response({"error": "Item type should be 'token' or 'collection'"}, status=status.HTTP_400_BAD_REQUEST)
        items[item_type].objects.filter(status=Status.PENDING, id=item_id).delete()
        return Response("success", status=status.HTTP_200_OK)


@api_view(http_method_names=['GET'])
def get_total_count(request):
        tokens_count = Token.token_objects.committed().count()
        verified_users_count = AdvUser.objects.filter(is_verificated=True).count()
        collections_count = Collection.objects.exclude(name__in=(config.COLLECTION_721, config.COLLECTION_1155)).count()
        time_delta = timezone.now() - timedelta(days=1)
        users_active_daily = AdvUser.objects.filter(last_login__gte=time_delta).count()
        response_data = {
            "total_tokens": tokens_count,
            "total_collections": collections_count,
            "verified_users": verified_users_count,
            "users_active_daily": users_active_daily,
        }
        return Response(response_data, status=status.HTTP_200_OK)
