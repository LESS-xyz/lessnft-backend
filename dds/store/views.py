from dds.accounts.models import AdvUser, MasterUser
from dds.activity.models import BidsHistory, ListingHistory, UserAction
from dds.consts import DECIMALS
from dds.settings import *
from dds.store.api import (check_captcha, get_dds_email_connection, validate_bid, token_search, collection_search)
from dds.store.services.ipfs import create_ipfs, get_ipfs_by_hash, send_to_ipfs

from dds.store.models import Bid, Collection, Ownership, Status, Tags, Token
from dds.store.serializers import (
    TokenPatchSerializer, 
    TokenSerializer,
    TokenFullSerializer,
    CollectionSlimSerializer,
    CollectionSerializer,
    HotCollectionSerializer,
    BetSerializer,
    BidSerializer,
)
from dds.utilities import sign_message, get_page_slice
from django.core.exceptions import ObjectDoesNotExist
from django.core.mail import send_mail
from django.db.models import Exists, OuterRef, Q
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from web3 import HTTPProvider, Web3

from dds.accounts.api import user_search
from dds.settings import NETWORK_SETTINGS, WETH_ADDRESS
from contracts import (
    EXCHANGE,
    WETH_CONTRACT
)
from dds.rates.api import get_decimals


transfer_tx = openapi.Response(
    description='Response with prepared transfer tx',
    schema=openapi.Schema(
        type=openapi.TYPE_ARRAY,
        items=openapi.Items(type=openapi.TYPE_OBJECT,
        properties={
            'tx': openapi.Schema(type=openapi.TYPE_STRING)
        }
    ))
)


create_response = openapi.Response(
    description='Response with created token',
    schema=openapi.Schema(
        type=openapi.TYPE_ARRAY,
        items=openapi.Items(type=openapi.TYPE_OBJECT,
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
    ))
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
            'amount': openapi.Schema(type=openapi.TYPE_NUMBER),
            'feeAddresses': openapi.Schema(type=openapi.TYPE_ARRAY, items=openapi.Items(type=openapi.TYPE_STRING)),
            'feeAmount': openapi.Schema(type=openapi.TYPE_ARRAY, items=openapi.Items(type=openapi.TYPE_NUMBER)),
            'signature': openapi.Schema(type=openapi.TYPE_STRING),
        }
    )
)

not_found_response = 'user not found'
try:
    master_user = MasterUser.objects.get()
    service_fee = master_user.commission
except:
    print('master user not found, please add him for correct backend start')

class SearchView(APIView):
    '''
    View for search items in shop.
    searching has simple 'contains' logic.
    '''
    @swagger_auto_schema(
        operation_description="post search pattern",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'text': openapi.Schema(type=openapi.TYPE_STRING),
                'page': openapi.Schema(type=openapi.TYPE_NUMBER)}),
        responses={200: TokenSerializer(many=True)},
    )
    def post(self, request):
        request_data = request.data
        words = request_data.get('text')
        page = request_data.get('page')
        params = request.query_params
        sort = params.get('type', 'items')

        search_result = globals()[SEARCH_TYPES[sort] + '_search'](words, page, user=request.user, **params)

        return Response(search_result, status=status.HTTP_200_OK)


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
            }),
        responses={200: create_response},
    )
    def post(self, request):
        request_data = request.data
        standart = request_data.get('standart')
        creator = request.user
        token_collection_id = request_data.get('collection')
        
        try:
            if isinstance(token_collection, int) or token_collection_id.isdigit():
                int_token_collection_id = int(token_collection_id)  
            else:
                int_token_collection_id = None
            token_collection = Collection.objects.get(
                Q(id=int_token_collection_id) | Q(short_url=token_collection_id)
            )
        except:
            return Response({'error': 'Collection not found'}, status=status.HTTP_400_BAD_REQUEST)
        
        if standart != token_collection.standart:
            return Response({'standart': 'collections type mismatch'}, status=status.HTTP_400_BAD_REQUEST)

        if Token.objects.filter(name=request_data.get('name')):
            return Response({'name': 'name already used'}, status=status.HTTP_400_BAD_REQUEST)

        ipfs = create_ipfs(request)
        if standart == 'ERC721':
            signature = sign_message(['address', 'string'], [token_collection.address, ipfs])
            amount = 1
        else:
            amount = request_data.get('total_supply')
            signature = sign_message(['address', 'string', 'uint256'], [token_collection.address, ipfs, int(amount)])

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
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'name': openapi.Schema(type=openapi.TYPE_STRING),
                'standart': openapi.Schema(type=openapi.TYPE_STRING),
                'avatar': openapi.Schema(type=openapi.TYPE_STRING),
                'symbol': openapi.Schema(type=openapi.TYPE_STRING),
                'description': openapi.Schema(type=openapi.TYPE_STRING),
                'short_url': openapi.Schema(type=openapi.TYPE_STRING),
            },
            required=['name', 'creator', 'avatar', 'symbol', 'standart']),
        responses={200: CollectionSlimSerializer},
    )
    def post(self, request):
        name = request.data.get('name')
        symbol = request.data.get('symbol')
        short_url = request.data.get('short_url')
        standart = request.data.get('standart')
        owner = request.user

        is_unique, response = Collection.collection_is_unique(name, symbol, short_url)
        if not is_unique:
            return response

        if standart not in ["ERC721", "ERC1155"]:
            return Response('invalid collection type', status=status.HTTP_400_BAD_REQUEST)

        initial_tx = Collection.create_contract(name, symbol, standart, owner)
        return Response(initial_tx, status=status.HTTP_200_OK)


class SaveCollectionView(APIView):
    '''
    View for save collection in database. Should be called after successfull minting.
    '''
    permission_classes = [IsAuthenticated]
    @swagger_auto_schema(
        operation_description="collection_save",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'tx_hash': openapi.Schema(type=openapi.TYPE_STRING),
                'name': openapi.Schema(type=openapi.TYPE_STRING),
                'standart': openapi.Schema(type=openapi.TYPE_STRING),
                'avatar': openapi.Schema(type=openapi.TYPE_STRING),
                'symbol': openapi.Schema(type=openapi.TYPE_STRING),
                'description': openapi.Schema(type=openapi.TYPE_STRING),
                'short_url': openapi.Schema(type=openapi.TYPE_STRING),
            }),
        responses={200: CollectionSlimSerializer},
    )
    def post(self, request):
        collection = Collection()
        media = request.FILES.get('avatar')
        if media:
            ipfs = send_to_ipfs(media)
        else:
            ipfs = None
        collection.save_in_db(request, ipfs)
        response_data = CollectionSlimSerializer(collection).data
        return Response(response_data, status=status.HTTP_200_OK)


class GetOwnedView(APIView):
    '''
    View for getting all items owned by address
    '''
    @swagger_auto_schema(
        operation_description="get tokens owned by address",
        responses={200: TokenSerializer(many=True), 401: not_found_response},
    )

    def get(self, request, address, page):
        try:
            user = AdvUser.objects.get(username=address)
        except ObjectDoesNotExist:
            return Response({'error': not_found_response}, status=status.HTTP_401_UNAUTHORIZED)

        tokens = Token.objects.filter(Q(owner=user) | Q(owners=user)).exclude(status=Status.BURNED).order_by('-id')

        start, end = get_page_slice(page, len(tokens))

        token_list = tokens[start:end]
        response_data = TokenSerializer(token_list, many=True, context={"user": request.user}).data
        return Response(response_data, status=status.HTTP_200_OK)


class GetCreatedView(APIView):
    '''
    View for getting all items created by address
    '''
    @swagger_auto_schema(
        operation_description="get tokens created by address",
        responses={200: TokenSerializer(many=True), 401: not_found_response},
    )

    def get(self, request, address, page):
        try:
            user = AdvUser.objects.get(username=address)
        except ObjectDoesNotExist:
            return Response({'error': not_found_response}, status=status.HTTP_401_UNAUTHORIZED)

        tokens = Token.objects.filter(creator=user).exclude(status=Status.BURNED).order_by('-id')

        start, end = get_page_slice(page, len(tokens))
        token_list = tokens[start:end]
        response_data = TokenSerializer(token_list, many=True, context={"user": request.user}).data
        return Response(response_data, status=status.HTTP_200_OK)


class GetLikedView(APIView):
    '''
    View for getting all items liked by address
    '''
    @swagger_auto_schema(
        operation_description="get tokens liked by address",
        responses={200: TokenSerializer(many=True), 401: not_found_response},
    )

    def get(self, request, address, page):
        try:
            user = AdvUser.objects.get(username=address)
        except ObjectDoesNotExist:
            return Response({'error': not_found_response}, status=status.HTTP_401_UNAUTHORIZED)

        # get users associated with the model UserAction
        ids = user.followers.all().values_list('user')
        
        # get tokens that users like
        tokens_action = UserAction.objects.filter(method='like', user__in=ids).order_by('-date')
        
        tokens = [action.token for action in tokens_action]

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
            token = Token.objects.get(id=id)
        except ObjectDoesNotExist:
            return Response('token not found', status=status.HTTP_401_UNAUTHORIZED)
        if token.status == Status.BURNED:
            return Response({'error': 'burned'}, status=status.HTTP_404_NOT_FOUND)
        response_data = TokenFullSerializer(token, context={"user": request.user}).data
        return Response(response_data, status=status.HTTP_200_OK)

    @swagger_auto_schema(
        operation_description="update owned token info",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'selling': openapi.Schema(type=openapi.TYPE_BOOLEAN),
                'price': openapi.Schema(type=openapi.TYPE_NUMBER),
                'currency': openapi.Schema(type=openapi.TYPE_STRING)
            },
        ),
        responses={200: TokenFullSerializer, 401: not_found_response, 400: "this token doesn't belong to you"},
    )
    def patch(self, request, id):
        request_data = request.data.copy()
        user = request.user

        try:
            token = Token.objects.get(id=id)
        except ObjectDoesNotExist:
            return Response({'error': not_found_response}, status=status.HTTP_401_UNAUTHORIZED)

        if token.status == Status.BURNED:
            return Response({'error': 'burned'}, status=status.HTTP_404_NOT_FOUND)

        if token.standart == 'ERC721':
            if token.owner.username != user.username:
                return Response({'error': "this token doesn't belong to you"}, status=status.HTTP_400_BAD_REQUEST)
        else:
            if not Ownership.objects.filter(token=token, owner=user):
                return Response({'error': "this token doesn't belong to you"}, status=status.HTTP_400_BAD_REQUEST)

        if request_data.get('price'):
            request_data['price'] = int(request_data['price'] * get_decimals(request_data.get('currency')))

        if request_data.get('minimal_bid'):
            request_data['minimal_bid'] = int(float(request_data['minimal_bid']) * get_decimals(request_data.get('currency')))
            print('minimal bid 1:', request_data['minimal_bid'])

        if token.standart == 'ERC1155':
            selling = request_data.pop('selling')
            if request_data.get('price'):
                price = request_data.pop('price')
            else:
                price = None
            if request_data.get('minimal_bid'):
                minimal_bid = float(request_data.pop('minimal_bid'))
                print('minimal bid 2:', minimal_bid)
            else:
                minimal_bid = None
            print('result minimal bid:', minimal_bid)

        serializer = TokenPatchSerializer(token, data=request_data, partial=True)

        if serializer.is_valid():
            serializer.save()
            print('saved')
        else:
            print('serializer not valid')

        #1155 specific ownership and token changes
        if token.standart == 'ERC1155':
            ownership = Ownership.objects.get(owner=user, token=token)
            if selling is not None:
                ownership.selling = selling
            ownership.price = price
            if token.price and ownership.price:
                if token.price > ownership.price:
                    token.price = ownership.price
                    token.full_clean()
                    token.save()
            else:
                token.price = ownership.price
                token.full_clean()
                token.save()
            if minimal_bid:
                print('minimal bet is exist')
                ownership.minimal_bid = minimal_bid
                if token.minimal_bid:
                    if token.minimal_bid > ownership.minimal_bid:
                        token.minimal_bid = ownership.minimal_bid
                        token.full_clean()
                        token.save()
            ownership.full_clean()
            ownership.save()
            token.selling = False
            token.save()

        response_data = TokenFullSerializer(token, context={"user": request.user}).data
        print('token min bid:', token.minimal_bid)
        try:
            price
        except UnboundLocalError:
            price = None
        try:
            selling
        except UnboundLocalError:
            selling = None
        if ((token.standart=='ERC721' and token.selling) or selling) and (price or request_data['price']):
            if token.standart == 'ERC1155':
                ownership = Ownership.objects.filter(
                    token=token,
                    owner=user
                ).first()
                quantity = ownership.quantity
                price = ownership.price
            else:
                quantity = 0
                price = token.price
            ListingHistory.objects.create(
                token=token,
                user=user,
                quantity=quantity,
                price=price
            )

        return Response(response_data, status=status.HTTP_200_OK)


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
        ]
    )
    def get(self, request, page):
        sort = request.query_params.get('sort', 'recent')
        tag = request.query_params.get('tag')

        order = SORT_STATUSES[sort]

        if tag:
            tokens = Token.objects.filter(tags__name__contains=tag).exclude(status=Status.BURNED).order_by(order)
        else:
            tokens = Token.objects.exclude(status=Status.BURNED).order_by(order)
        if sort in ('cheapest', 'highest'):
            tokens = tokens.exclude(price=None).exclude(selling=False).exclude(status=Status.BURNED)
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
        responses={200: HotCollectionSerializer(many=True)},
    )
    def get(self, request):
        collections = Collection.objects.exclude(name__in=(
            COLLECTION_721, 
            COLLECTION_1155,
        )).filter(Exists(Token.objects.filter(collection__id=OuterRef('id')))).order_by('-id')[:5]
        response_data = HotCollectionSerializer(collections, many=True).data
        return Response(response_data, status=status.HTTP_200_OK)


class GetCollectionView(APIView):
    '''
    View for get collection info in shop.
    '''
    @swagger_auto_schema(
        operation_description="get collection info",
        responses={200: CollectionSerializer, 400: 'collection not found'},
    )

    def get(self, request, param, page):
        try:
            id_ = int(param) if isinstance(param, int) or param.isdigit() else None
            collection = Collection.objects.get(
                Q(id=id_) | Q(short_url=param)
            )
        except ObjectDoesNotExist:
            return Response({'error': 'collection not found'}, status=status.HTTP_400_BAD_REQUEST)

        tokens = Token.objects.filter(collection=collection).exclude(status=Status.BURNED)

        start, end = get_page_slice(page, len(tokens))
        token_list = tokens[start:end]
        response_data = CollectionSerializer(collection, context={"tokens": token_list}).data
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
                'id': openapi.Schema(type=openapi.TYPE_NUMBER),
                'address': openapi.Schema(type=openapi.TYPE_STRING)
            }),
        responses={200: transfer_tx, 400: "you can not transfer tokens that don't belong to you"},
    )
    def post(self, request, token):
        #get token, collection and user
        id = request.data.get('id')
        new_owner = Web3.toChecksumAddress(request.data.get('address'))
        transferring_token = Token.objects.get(id=id)
        if transferring_token.status == Status.BURNED:
            return Response({'error': 'burned'}, status=status.HTTP_404_NOT_FOUND)
        if transferring_token.internal_id is None:
            return Response('token is not validated yet, please wait up to 5 minutes. If problem persists,'
                            'please contact us through support form', status=status.HTTP_400_BAD_REQUEST)
        user = request.user

        #construct tx
        current_owner = Web3.toChecksumAddress(user.username)

        if current_owner.lower() != transferring_token.owner.username.lower():
            return Response({'error': "you can not transfer tokens that don't belong to you"})

        initial_tx = transferring_token.transfer(new_owner)

        return Response({'initial_tx': initial_tx}, status=status.HTTP_200_OK)


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
                'tokenAmount': openapi.Schema(type=openapi.TYPE_NUMBER)
            }),
        responses={200:buy_token_response, 400:"you cant buy token"}
    )
    def post(self, request):
        #get token and collection
        
        try:
            token_id = int(request.data.get('id'))
        except TypeError:
            token_id = None
        try:
            seller_id = int(request.data.get('sellerId'))
        except TypeError:
            seller_id = None
        tradable_token = Token.objects.get(id=token_id)
        if tradable_token.status == Status.BURNED:
            return Response({'error': 'burned'}, status=status.HTTP_404_NOT_FOUND)
        if tradable_token.internal_id is None:
            return Response('token is not validated yet, please wait up to 5 minutes. If problem persists,'
                            'please contact us through support form', status=status.HTTP_400_BAD_REQUEST)
        token_amount = int(request.data.get('tokenAmount'))

        if tradable_token.selling is False:
            return Response('token not selling', status=status.HTTP_403_FORBIDDEN)
        
        if tradable_token.standart == 'ERC721' and token_amount != 0:
            return Response('wrong token amount', status=status.HTTP_400_BAD_REQUEST)
            
        elif tradable_token.standart == 'ERC1155' and token_amount == 0:
            return Response('wrong token amount', status=status.HTTP_400_BAD_REQUEST) 

        buyer = request.user
        try:
            if seller_id:
                int_id = int(seller_id) if isinstance(seller_id, int) or seller_id.isdigit() else None
                seller = AdvUser.objects.get(
                    Q(id=int_id) | Q(custom_url=seller_id)
                )
                ownership = Ownership.objects.filter(token__id=token_id, owner=seller).filter(selling=True)
                if not ownership:
                    return Response({'error': 'user is not owner or token is not on sell'})
            else:
                seller = None
        except ObjectDoesNotExist:
            return Response({'error': 'user not found'}, status=status.HTTP_400_BAD_REQUEST)

        master_account = MasterUser.objects.get()
    
        buy = tradable_token.buy_token(token_amount, buyer, master_account, seller)

        return buy


@api_view(http_method_names=['GET'])
def get_tags(request):
    tag_list = [tag.name for tag in Tags.objects.all()] 
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
        amount = int(request_data.get('amount'))
        quantity = int(request_data.get('quantity'))

        web3 = Web3(HTTPProvider(NETWORK_SETTINGS['ETH']['endpoint']))

        user = request.user

        #returns True if OK, or error message
        result = validate_bid(user, token_id, amount, WETH_CONTRACT, quantity)

        if result == 'OK':
            #create new bid or update old one
            bid = Bid.objects.get_or_create(user=user, token=Token.objects.get(id=token_id))[0]
            if bid.amount and bid.amount > amount:
                return Response({'error': 'you cannot lower your bid'}, status=status.HTTP_400_BAD_REQUEST)
            bid.amount = amount
            bid.quantity = quantity
            bid.full_clean()
            bid.save()

            #construct approve tx if not approved yet:
            allowance = weth_contract.functions.allowance(web3.toChecksumAddress(user.username),
                                                          web3.toChecksumAddress(EXCHANGE_ADDRESS)).call()
            user_balance = weth_contract.functions.balanceOf(Web3.toChecksumAddress(user.username)).call()
            if allowance < amount * quantity:
                tx_params = {
                    'chainId': web3.eth.chainId,
                    'gas': APPROVE_GAS_LIMIT,
                    'nonce': web3.eth.getTransactionCount(web3.toChecksumAddress(user.username), 'pending'),
                    'gasPrice': web3.eth.gasPrice,
                }
                initial_tx = weth_contract.functions.approve(web3.toChecksumAddress(EXCHANGE_ADDRESS), user_balance).buildTransaction(tx_params)
                return Response({'initial_tx': initial_tx}, status=status.HTTP_200_OK)

            else:
                bid.state = Status.COMMITTED
                bid.full_clean()
                bid.save()
                
                BidsHistory.objects.create(
                    token=bid.token,
                    user=bid.user,
                    price=bid.amount,
                    date=bid.created_at
                    )

                return Response({'bid created, allowance not needed'}, status=status.HTTP_200_OK)
        else:
            return Response({'error': result}, status=status.HTTP_400_BAD_REQUEST)


@api_view(http_method_names=['GET'])
@permission_classes([IsAuthenticated])
def get_bids(request, token_id):
    #validating token and user
    try:
        token = Token.objects.get(id=token_id)
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
        web3 = Web3(HTTPProvider(NETWORK_SETTINGS['ETH']['endpoint']))

        bets = Bid.objects.filter(token__id=token_id).order_by('-amount')
        max_bet = bets.first()
        if not max_bet:
            return Response(
                    {'invalid_bet': None, 'valid_bet': None},
                    status=status.HTTP_200_OK)
            
        user = max_bet.user
        amount = max_bet.amount
        quantity = max_bet.quantity

        check_valid = validate_bid(user, token_id, amount, WETH_CONTRACT, quantity)

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
                check_valid = validate_bid(user, token_id, amount, WETH_CONTRACT, quantity)
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

        master_account = MasterUser.objects.get()

        token = bet.token
        buyer = bet.user
        price = bet.amount

        seller = request.user
        if token.standart == 'ERC721':
            if seller != token.owner:
                return Response({'error': 'user is not owner or token is not on sell'})
        else:
            ownership = Ownership.objects.filter(token=token, owner=seller).first()
            if not ownership:
                return Response({'error': 'user is not owner or token is not on sell'})

        if token.standart == 'ERC721':
            token_amount = 0
            seller=None
        else:
            token_amount = min(bet.quantity, ownership.quantity)

        sell = token.buy_token(token_amount, buyer, master_account,seller=seller, price=price)
        return sell


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

        if check_captcha(response):
            connection = get_dds_email_connection()
            text = """
                    Page: {page}
                    Message: {message}
                    """.format(page=page, message=message)

            send_mail(
                'Report from digital dollar store',
                text,
                DDS_HOST_USER,
                [DDS_MAIL],
                connection=connection,
            )
            print('message sent')

            return Response('OK', status=status.HTTP_200_OK)
        else:
            return Response('you are robot. go away, robot!', status=status.HTTP_400_BAD_REQUEST)


class SetCoverView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description='set cover',
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'id': openapi.Schema(type=openapi.TYPE_NUMBER),
                'cover': openapi.Schema(type=openapi.TYPE_OBJECT)
            }
        ),
        responses={200: 'OK', 400: 'error'}
    )
    def post(self, request):
        user = request.user
        collection_id = request.data.get('id')
        try:
            int_collection_id = int(collection_id) if isinstance(collection_id, int) or collection_id.isdigit() else None
            collection = Collection.objects.get(
                Q(id=int_collection_id) | Q(short_url=collection_id)
            )
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
    return Response(service_fee, status=status.HTTP_200_OK)


@api_view(http_method_names=['GET'])
def get_favorites(request):
    token_list = Token.objects.filter(is_favorite=True).order_by("-updated_at")
    response_data = TokenSerializer(token_list, many=True, context={"user": request.user}).data
    return Response(response_data, status=status.HTTP_200_OK)


@api_view(http_method_names=['GET'])
def get_hot_bids(request):
    bids = Bid.objects.filter(state=Status.COMMITTED).order_by('-id')[:6]
    token_list= [bid.token for bid in bids]
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

        if check_captcha(response):
            connection = get_dds_email_connection()
            text = """
                    Email: {email}
                    Message: {message}
                    """.format(email=email, message=message)

            send_mail(
                'Support form from digital dollar store',
                text,
                DDS_HOST_USER,
                [DDS_MAIL],
                connection=connection,
            )
            print('message sent')

            return Response('OK', status=status.HTTP_200_OK)
        else:
            return Response('you are robot. go away, robot!', status=status.HTTP_400_BAD_REQUEST)
