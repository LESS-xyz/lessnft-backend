from dds.accounts.models import AdvUser, MasterUser
from dds.accounts.api import user_search
from dds.activity.models import BidsHistory, ListingHistory, UserAction
from dds.consts import DECIMALS
from dds.rates.api import calculate_amount
from dds.settings import *
from dds.store.api import (check_captcha, token_search, collection_search,
                           get_dds_email_connection, validate_bid)
from dds.store.services.ipfs import create_ipfs

from dds.store.models import Bid, Collection, Ownership, Status, Tags, Token
from dds.store.serializers import TokenPatchSerializer
from dds.utilities import get_media_if_exists, sign_message
from django.core.exceptions import ObjectDoesNotExist
from django.core.mail import send_mail
from django.db.models import Exists, OuterRef, Q
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.authtoken.models import Token as AuthToken
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.views import APIView
from web3 import HTTPProvider, Web3

from dds.settings import NETWORK_SETTINGS
from contracts import (
    EXCHANGE,
    ERC721_FABRIC,
    ERC1155_FABRIC,
    WETH_CONTRACT
)

get_list_response = openapi.Response(
    description='Response with search results',
    schema=openapi.Schema(
        type=openapi.TYPE_ARRAY,
        items=openapi.Items(type=openapi.TYPE_OBJECT,
        properties={
            'id': openapi.Schema(type=openapi.TYPE_NUMBER),
            'name': openapi.Schema(type=openapi.TYPE_STRING),
            'media': openapi.Schema(type=openapi.TYPE_STRING),
            'total_supply': openapi.Schema(type=openapi.TYPE_NUMBER),
            'price': openapi.Schema(type=openapi.TYPE_NUMBER),
            'currency': openapi.Schema(type=openapi.TYPE_STRING),
            'USD_price': openapi.Schema(type=openapi.TYPE_NUMBER),
            'owner': openapi.Schema(type=openapi.TYPE_NUMBER),
            'creator': openapi.Schema(type=openapi.TYPE_NUMBER),
            'collection': openapi.Schema(type=openapi.TYPE_NUMBER),
            'description': openapi.Schema(type=openapi.TYPE_STRING),
            'details': openapi.Schema(type=openapi.TYPE_OBJECT),
            'creator_royalty': openapi.Schema(type=openapi.TYPE_NUMBER),
            'selling': openapi.Schema(type=openapi.TYPE_BOOLEAN)
        }
    ))
)

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


get_single_response = openapi.Response(
    description='Response with single response',
    schema=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'id': openapi.Schema(type=openapi.TYPE_NUMBER),
            'name': openapi.Schema(type=openapi.TYPE_STRING),
            'media': openapi.Schema(type=openapi.TYPE_STRING),
            'total_supply': openapi.Schema(type=openapi.TYPE_NUMBER),
            'available': openapi.Schema(type=openapi.TYPE_NUMBER),
            'price': openapi.Schema(type=openapi.TYPE_NUMBER),
            'currency': openapi.Schema(type=openapi.TYPE_STRING),
            'USD_price': openapi.Schema(type=openapi.TYPE_NUMBER),
            'owner': openapi.Schema(type=openapi.TYPE_NUMBER),
            'creator': openapi.Schema(type=openapi.TYPE_NUMBER),
            'collection': openapi.Schema(type=openapi.TYPE_NUMBER),
            'description': openapi.Schema(type=openapi.TYPE_STRING),
            'details': openapi.Schema(type=openapi.TYPE_OBJECT),
            'creator_royalty': openapi.Schema(type=openapi.TYPE_NUMBER),
            'selling': openapi.Schema(type=openapi.TYPE_BOOLEAN)
        }
    )
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

create_collection_response = openapi.Response(
    description='Response with created collection',
    schema=openapi.Schema(
        type=openapi.TYPE_ARRAY,
        items=openapi.Items(type=openapi.TYPE_OBJECT,
        properties={
            'id': openapi.Schema(type=openapi.TYPE_NUMBER),
            'name': openapi.Schema(type=openapi.TYPE_STRING),
            'avatar': openapi.Schema(type=openapi.TYPE_STRING),
            'address': openapi.Schema(type=openapi.TYPE_STRING),
        }
    ))
)

get_collection_response = openapi.Response(
    description='Response with created collection',
    schema=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'id': openapi.Schema(type=openapi.TYPE_NUMBER),
            'name': openapi.Schema(type=openapi.TYPE_STRING),
            'avatar': openapi.Schema(type=openapi.TYPE_STRING),
            'address': openapi.Schema(type=openapi.TYPE_STRING),
            'tokens': openapi.Schema(type=openapi.TYPE_OBJECT),
        }
    ))

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
        responses={200: get_list_response},
    )
    def post(self, request):
        request_data = request.data
        words = request_data.get('text')
        page = request_data.get('page')
        sort = request.query_params.get('type', 'items')


        search_result = globals()[SEARCH_TYPES[sort] + '_search'](words, page)

        return Response(search_result, status=status.HTTP_200_OK)


class CreateView(APIView):
    '''
    View for create token transaction.
    '''
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
                'creator': openapi.Schema(type=openapi.TYPE_STRING),
                'creator_royalty': openapi.Schema(type=openapi.TYPE_NUMBER),
                'collection': openapi.Schema(type=openapi.TYPE_NUMBER),
                'details': openapi.Schema(type=openapi.TYPE_OBJECT),
            }),
        responses={200: create_response},
    )
    def post(self, request):
        request_data = request.data
        creator = request_data.get('creator')
        standart = request_data.get('standart')

        try:
            creator = AdvUser.objects.get(auth_token=creator)
        except:
            return Response({'error': 'User not found'}, status=status.HTTP_400_BAD_REQUEST)

        token_collection_id = request_data.get('collection')
        
        try:
            token_collection = Collection.objects.get(id=token_collection_id)
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
        return Response({'initial_tx': initial_tx}, status=status.HTTP_200_OK)


class SaveView(APIView):
    '''
    View for saving token in database. Should be called after successfull minting or contain minting logic.
    '''

    @swagger_auto_schema(
        operation_description="token_creation",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'tx_hash': openapi.Schema(type=openapi.TYPE_STRING),
                'name': openapi.Schema(type=openapi.TYPE_STRING),
                'standart': openapi.Schema(type=openapi.TYPE_STRING),
                'total_supply': openapi.Schema(type=openapi.TYPE_NUMBER),
                'currency': openapi.Schema(type=openapi.TYPE_STRING),
                'description': openapi.Schema(type=openapi.TYPE_STRING),
                'price': openapi.Schema(type=openapi.TYPE_NUMBER),
                'creator': openapi.Schema(type=openapi.TYPE_NUMBER),
                'creator_royalty': openapi.Schema(type=openapi.TYPE_NUMBER),
                'collection': openapi.Schema(type=openapi.TYPE_NUMBER),
                'details': openapi.Schema(type=openapi.TYPE_OBJECT),
                'selling': openapi.Schema(type=openapi.TYPE_STRING),
            }),
        responses={200: create_response},
    )
    def post(self, request):
        token = Token()
        token.save_in_db(request)

        # response with created token info
        collection_avatar = get_media_if_exists(token.collection, 'avatar')
        token_owners = []
        if token.standart == 'ERC1155':
            owners = token.owners.all()
            available = 0
            for owner in owners:
                holder = {
                    'id': owner.id,
                    'name': owner.get_name(),
                    'avatar': get_media_if_exists(owner, 'avatar'),
                    'quantity': Ownership.objects.get(owner=owner, token=token).quantity
                    }
                token_owners.append(holder)
                if Ownership.objects.get(owner=owner, token=token).selling:
                    available += Ownership.objects.get(owner=owner, token=token).quantity
        else:
            owner = {
                'id': token.owner.id,
                'name': token.owner.get_name(),
                'avatar': get_media_if_exists(token.owner, 'avatar'),
                }
            token_owners.append(owner)
            if token.selling:
                available = 1
            else:
                available = 0
        response_data = {
                'id': token.id, 
                'name': token.name, 
                'media': token.media, 
                'total_supply': token.total_supply,
                'available': available,
                'price': (token.price / DECIMALS[token.currency] if token.price else None), 
                'currency': token.currency,         
                'USD_price': (calculate_amount(token.price, token.currency)[0] if token.price else None), 
                'owner': token_owners,
                'creator': {
                    'id': token.creator.id,
                    'name': token.creator.get_name(),
                    'avatar': ALLOWED_HOSTS[0] + token.creator.avatar.url
                },
                'collection': {
                    'id': token.collection.id,
                    'avatar': collection_avatar,
                    'name': token.collection.name
                },
                'description': token.description,
                'details': token.details, 
                'royalty': token.creator_royalty, 
                'selling': token.selling
        }

        return Response(response_data, status=status.HTTP_200_OK)

class CreateCollectionView(APIView):
    '''
    View for create collection transaction..
    '''

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
                'creator': openapi.Schema(type=openapi.TYPE_STRING)
            },
            required=['name', 'creator', 'avatar', 'symbol', 'standart']),
        responses={200: create_collection_response},
    )
    def post(self, request):
        web3 = Web3(HTTPProvider(NETWORK_SETTINGS['ETH']['endpoint']))

        request_data = request.data
        name = request_data.get('name')
        symbol = request_data.get('symbol')
        short_url = request_data.get('short_url')

        if Collection.objects.filter(name=request_data.get('name')):
            return Response({'name': 'this collection name is occupied'}, status=status.HTTP_400_BAD_REQUEST)
        if Collection.objects.filter(symbol=request_data.get('symbol')):
            return Response({'symbol': 'this collection symbol is occupied'}, status=status.HTTP_400_BAD_REQUEST)
        if short_url and Collection.objects.filter(short_url=short_url):
            return Response({'short_url': 'this collection short_url is occupied'}, status=status.HTTP_400_BAD_REQUEST)

        baseURI = '/ipfs/'

        creator = request_data.get('creator')
        standart = request_data.get('standart')

        token = AuthToken.objects.get(key=creator)
        owner = AdvUser.objects.get(id=token.user_id)

        address = SIGNER_ADDRESS
        signature = sign_message(['address'], [address])

        tx_params = {
            'chainId': web3.eth.chainId,
            'gas': COLLECTION_CREATION_GAS_LIMIT,
            'nonce': web3.eth.getTransactionCount(web3.toChecksumAddress(owner.username), 'pending'),
            'gasPrice': web3.eth.gasPrice,
        }

        if standart == 'ERC721':
            myContract = web3.eth.contract(
                address=web3.toChecksumAddress(ERC721_FABRIC['address']),
                abi=ERC721_FABRIC['abi'])

            initial_tx = myContract.functions.makeERC721(
                name, 
                symbol, 
                baseURI, 
                address, 
                signature
            ).buildTransaction(tx_params)

        elif standart == 'ERC1155':
            myContract = web3.eth.contract(
                address=web3.toChecksumAddress(ERC1155_FABRIC['address']),
                abi=ERC1155_FABRIC['abi'])
                
            initial_tx = myContract.functions.makeERC1155(
                baseURI, 
                address, 
                signature
            ).buildTransaction(tx_params)

        else:
            return Response('invalid collection type', status=status.HTTP_400_BAD_REQUEST)

        return Response(initial_tx, status=status.HTTP_200_OK)


class SaveCollectionView(APIView):
    '''
    View for save collection in database. Should be called after successfull minting.
    '''

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
                'creator': openapi.Schema(type=openapi.TYPE_STRING)
            }),
        responses={200: 'OK'},
    )
    def post(self, request):
        collection = Collection()
        collection.save_in_db(request)

        avatar = get_media_if_exists(collection, 'avatar')

        response_data = {
            'id': collection.id, 
            'name': collection.name, 
            'avatar': avatar, 
            'address': collection.address
        }

        return Response(response_data, status=status.HTTP_200_OK)


class GetOwnedView(APIView):
    '''
    View for getting all items owned by address
    '''
    @swagger_auto_schema(
        operation_description="get tokens owned by address",
        responses={200: get_list_response, 401: not_found_response},
    )

    def get(self, request, address, page):
        try:
            user = AdvUser.objects.get(username=address)
        except ObjectDoesNotExist:
            return Response({'error': not_found_response}, status=status.HTTP_401_UNAUTHORIZED)

        tokens = Token.objects.filter(Q(owner=user) | Q(owners=user)).exclude(status=Status.BURNED).order_by('-id')
        token_list = []

        start = (page - 1) * 50
        end = page * 50 if len(tokens) >= page * 50 else None

        for token in tokens[start:end]:
            collection_avatar = get_media_if_exists(token.collection, 'avatar')

            token_owners = []
            if token.standart == 'ERC1155':
                owners = token.owners.all()
                available = 0
                for owner in owners[:3]:
                    holder = {
                        'id': owner.id,
                        'name': owner.get_name(),
                        'avatar': get_media_if_exists(owner, 'avatar'),
                        'quantity': Ownership.objects.get(owner=owner, token=token).quantity
                        }
                    token_owners.append(holder)
                for owner in owners:
                    if Ownership.objects.get(owner=owner, token=token).selling:
                        available += Ownership.objects.get(owner=owner, token=token).quantity
            else:
                owner = {
                    'id': token.owner.id,
                    'name': token.owner.get_name(),
                    'avatar': get_media_if_exists(token.owner, 'avatar'),
                    }
                token_owners.append(owner)
                if token.selling:
                    available = 1
                else:
                    available = 0

            token_list.append({
                'id': token.id, 
                'name': token.name, 
                'standart': token.standart,
                'media': token.media, 
                'total_supply': token.total_supply,
                'available': available,
                'price': token.price / DECIMALS[token.currency] if token.price else None,
                'currency': token.currency,
                'USD_price': calculate_amount(token.price, token.currency)[0] if token.price else None,
                'owners': token_owners,
                'creator': {
                    'id': token.creator.id,
                    'name': token.creator.get_name(),
                    'avatar': ALLOWED_HOSTS[0] + token.creator.avatar.url
                },
                'collection': {
                    'id': token.collection.id,
                    'avatar': collection_avatar,
                    'name': token.collection.name
                },
                'description': token.description, 
                'royalty': token.creator_royalty,
                'details': token.details, 
                'selling': token.selling
            })

        return Response(token_list, status=status.HTTP_200_OK)


class GetCreatedView(APIView):
    '''
    View for getting all items created by address
    '''
    @swagger_auto_schema(
        operation_description="get tokens created by address",
        responses={200: get_list_response, 401: not_found_response},
    )

    def get(self, request, address, page):
        try:
            user = AdvUser.objects.get(username=address)
        except ObjectDoesNotExist:
            return Response({'error': not_found_response}, status=status.HTTP_401_UNAUTHORIZED)

        tokens = Token.objects.filter(creator=user).exclude(status=Status.BURNED).order_by('-id')
        token_list = []

        start = (page - 1) * 50
        end = page * 50 if len(tokens) >= page * 50 else None

        for token in tokens[start:end]:
            collection_avatar = get_media_if_exists(token.collection, 'avatar')

            token_owners = []
            if token.standart == 'ERC1155':
                owners = token.owners.all()
                available = 0
                for owner in owners:
                    holder = {
                        'id': owner.id,
                        'name': owner.get_name(),
                        'avatar': get_media_if_exists(owner, 'avatar'),
                        'quantity': Ownership.objects.get(owner=owner, token=token).quantity
                        }
                    token_owners.append(holder)
                    if Ownership.objects.get(owner=owner, token=token).selling:
                        available += Ownership.objects.get(owner=owner, token=token).quantity
            else:
                owner = {
                    'id': token.owner.id,
                    'name': token.owner.get_name(),
                    'avatar': get_media_if_exists(token.owner, 'avatar'),
                    }
                token_owners.append(owner)
                if token.selling:
                    available = 1
                else:
                    available = 0


            token_list.append({
                'id': token.id, 
                'name': token.name, 
                'standart': token.standart, 
                'media': token.media, 
                'total_supply': token.total_supply,
                'available': available, 
                'price': token.price / DECIMALS[token.currency] if token.price else None,
                'currency': token.currency,
                'USD_price': calculate_amount(token.price, token.currency)[0] if token.price else None,
                'owners': token_owners,
                'creator': {
                    'id': token.creator.id,
                    'name': token.creator.get_name(),
                    'avatar': ALLOWED_HOSTS[0] + token.creator.avatar.url
                },
                'collection': {
                    'id': token.collection.id,
                    'avatar': collection_avatar,
                    'name': token.collection.name
                },
                'description': token.description, 
                'details': token.details,
                'royalty': token.creator_royalty, 
                'selling': token.selling
            })
        
        return Response(token_list, status=status.HTTP_200_OK)


class GetLikedView(APIView):
    '''
    View for getting all items liked by address
    '''
    @swagger_auto_schema(
        operation_description="get tokens liked by address",
        responses={200: get_list_response, 401: not_found_response},
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
        token_list = []

        start = (page - 1) * 50
        end = page * 50 if len(tokens) >= page * 50 else None

        for token in tokens[start:end]:
            collection_avatar = get_media_if_exists(token.collection, 'avatar')

            token_owners = []
            if token.standart == 'ERC1155':
                owners = token.owners.all()
                available = 0
                for owner in owners:
                    holder = {
                        'id': owner.id,
                        'name': owner.get_name(),
                        'avatar': get_media_if_exists(owner, 'avatar'),
                        'quantity': Ownership.objects.get(owner=owner, token=token).quantity
                        }
                    token_owners.append(holder)
                    if Ownership.objects.get(owner=owner, token=token).selling:
                        available += Ownership.objects.get(owner=owner, token=token).quantity
            else:
                owner = {
                    'id': token.owner.id,
                    'name': token.owner.get_name(),
                    'avatar': get_media_if_exists(token.owner, 'avatar'),
                    }
                token_owners.append(owner)
                if token.selling:
                    available = 1
                else:
                    available = 0

            token_list.append({
                'id': token.id, 
                'name': token.name, 
                'standart': token.standart, 
                'media': token.media, 
                'total_supply': token.total_supply,
                'available': available, 
                'price': token.price / DECIMALS[token.currency] if token.price else None,
                'currency': token.currency,
                'USD_price': calculate_amount(token.price, token.currency)[0] if token.price else None,
                'owners': token_owners,
                'creator': {
                    'id': token.creator.id,
                    'name': token.creator.get_name(),
                    'avatar': ALLOWED_HOSTS[0] + token.creator.avatar.url
                },
                'collection': {
                    'id': token.collection.id,
                    'avatar': collection_avatar,
                    'name': token.collection.name
                },
                'description': token.description, 
                'details': token.details,
                'royalty': token.creator_royalty, 
                'selling': token.selling
            })

        return Response(token_list, status=status.HTTP_200_OK)


class GetView(APIView):
    '''
    View for get token info.
    '''
    @swagger_auto_schema(
        operation_description="get token info",
        responses={200: get_single_response, 401: not_found_response},
    )

    def get(self, request, id):
        try:
            token = Token.objects.get(id=id)
        except ObjectDoesNotExist:
            return Response('token not found', status=status.HTTP_401_UNAUTHORIZED)
        if token.status == Status.BURNED:
            return Response({'error': 'burned'}, status=status.HTTP_404_NOT_FOUND)
        collection_avatar = get_media_if_exists(token.collection, 'avatar')

        bids = Bid.objects.filter(token=token).order_by('-amount')
        bid_list = []
        for bid in bids:
            bid_list.append({
                'id': bid.id,
                'bidder': bid.user.get_name(),
                'bidderid': bid.user.id,
                'bidderavatar': ALLOWED_HOSTS[0] + bid.user.avatar.url,
                'quantity': bid.quantity,
                'amount': bid.amount / DECIMALS[bid.token.currency],
                'currency': bid.token.currency
            })

        token_history = []
        history = token.tokenhistory_set.exclude(method='Burn').order_by('-id')

        if history != []:
            for action in history:
                owner = {
                    'id': action.new_owner.id,
                    'name': action.new_owner.get_name(),
                    'avatar': get_media_if_exists(action.new_owner, 'avatar'),
                    'method': action.method,
                    'date': action.date,
                    'price': action.price / DECIMALS[action.token.currency] if action.price else None
                }
                token_history.append(owner)

        token_owners = []
        if token.standart == 'ERC1155':
            owners = token.owners.all()
            available = 0
            for owner in owners:
                holder = {
                        'id': owner.id,
                        'name': owner.get_name(),
                        'avatar': get_media_if_exists(owner, 'avatar'),
                        'quantity': Ownership.objects.get(owner=owner, token=token).quantity
                        }
                token_owners.append(holder)
                if Ownership.objects.get(owner=owner, token=token).selling:
                    available += Ownership.objects.get(owner=owner, token=token).quantity
        else:
            owner = {
                    'id': token.owner.id,
                    'name': token.owner.get_name(),
                    'avatar': get_media_if_exists(token.owner, 'avatar'),
                    }
            token_owners.append(owner)
            if token.selling:
                available = 1
            else:
                available = 0


        sellers_list = []
        sellers = Ownership.objects.filter(
            token=token, 
            price__isnull=False,
            selling=True
        ).order_by('price')
        for seller in sellers:
            seller_user = seller.owner
            sellers_list.append({
                'id': seller_user.id,
                'name': seller_user.get_name(),
                'avatar': get_media_if_exists(seller_user, 'avatar'),
                'quantity': seller.quantity,
                'price': seller.price
            })
        response_data = {
            'id': token.id, 
            'name': token.name, 
            'standart': token.standart, 
            'tags': [tag.name for tag in token.tags.all()],
            'media': token.media,
            'total_supply': token.total_supply,
            'available': available, 
            'price': (token.price / DECIMALS[token.currency] if token.price else None),
            'minimal_bid': token.minimal_bid / DECIMALS[token.currency] if token.minimal_bid else None,
            'currency': token.currency,
            'USD_price': (calculate_amount(token.price, token.currency)[0] if token.price else None), 
            'owners': token_owners,
            'history': token_history,
            'sellers': sellers_list,
            'creator': {
                'id': token.creator.id, 
                'name': token.creator.get_name(),
                'avatar': get_media_if_exists(token.creator, 'avatar')
            },
            'collection': {
                'id': token.collection.id, 
                'avatar': get_media_if_exists(token.collection, 'avatar'),
                'name': token.collection.name,
                'address': token.collection.address
            },
            'bids': bid_list,
            'description': token.description,
            'details': token.details,
            'royalty': token.creator_royalty, 
            'selling': token.selling,
            'like_count': token.useraction_set.count(),
            'service_fee': service_fee,
            'internl_id': token.internal_id,
            'owner_auction': token.get_owner_auction()
        }

        if token.standart == 'ERC1155':
            if not Ownership.objects.filter(token=token).filter(selling=True):
                response_data['selling'] = False
            else:
                response_data['selling'] = True

        return Response(response_data, status=status.HTTP_200_OK)

    @swagger_auto_schema(
        operation_description="update owned token info",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'AuthToken': openapi.Schema(type=openapi.TYPE_STRING),
                'selling': openapi.Schema(type=openapi.TYPE_BOOLEAN),
                'price': openapi.Schema(type=openapi.TYPE_NUMBER),
                'currency': openapi.Schema(type=openapi.TYPE_STRING)
            },
        ),
        responses={200: get_single_response, 401: not_found_response, 400: "this token doesn't belong to you"},
    )
    def patch(self, request, id):
        request_data = request.data.copy()
        user_token = request_data.pop('AuthToken')

        try:
            auth_token = AuthToken.objects.get(key=user_token)
            user = AdvUser.objects.get(id=auth_token.user_id)
        except ObjectDoesNotExist:
            return Response({'error': not_found_response}, status=status.HTTP_401_UNAUTHORIZED)

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
            request_data['price'] = int(request_data['price'] * DECIMALS[request_data.get('currency')])

        if request_data.get('minimal_bid'):
            request_data['minimal_bid'] = int(float(request_data['minimal_bid']) * DECIMALS[request_data.get('currency')])
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

        collection_avatar = get_media_if_exists(token.collection, 'avatar')
        token_owners = []

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
                        token.minimal_bid = ownership.minimal_bi
                        token.full_clean()
                        token.save()
            ownership.full_clean()
            ownership.save()
            token.selling = False
            token.save()

        #Further is just response creation
        if token.standart == 'ERC1155':
            owners = token.owners.all()
            available = 0
            for owner in owners:
                holder = {
                        'id': owner.id,
                        'name': owner.get_name(),
                        'avatar': get_media_if_exists(owner, 'avatar'),
                        'quantity': Ownership.objects.get(owner=owner, token=token).quantity
                        }
                token_owners.append(holder)
                if Ownership.objects.get(owner=owner, token=token).selling:
                    available += Ownership.objects.get(owner=owner, token=token).quantity
        else:
            owner = {
                    'id': token.owner.id,
                    'name': token.owner.get_name(),
                    'avatar': get_media_if_exists(token.owner, 'avatar'),
                    }
            token_owners.append(owner)
            if token.selling:
                available = 1
            else:
                available = 0


        token_history = []
        history = token.tokenhistory_set.all()

        if history != []:
            for action in history:
                owner = {
                    'id': action.new_owner.id,
                    'name': action.new_owner.get_name(),
                    'avatar': get_media_if_exists(action.new_owner, 'avatar'),
                    'method': action.method,
                    'date': action.date,
                    'price': action.price / DECIMALS[action.token.currency] if action.price else None
                }
                token_history.append(owner)

        sellers_list = []
        sellers = Ownership.objects.filter(
            token=token, 
            price__isnull=False,
            selling=True
        ).order_by('price')
        for seller in sellers:
            seller_user = seller.owner
            sellers_list.append({
                'id': seller_user.id,
                'name': seller_user.get_name(),
                'avatar': get_media_if_exists(seller_user, 'avatar'),
                'quantity': seller.quantity,
                'price': seller.price
            })

        bids = Bid.objects.filter(token=token).order_by('-amount')
        bid_list = []
        for bid in bids:
            bid_list.append({
                'id': bid.id,
                'bidder': bid.user.get_name(),
                'bidderid': bid.user.id,
                'bidderavatar': ALLOWED_HOSTS[0] + bid.user.avatar.url,
                'quantity': bid.quantity,
                'amount': bid.amount / DECIMALS[bid.token.currency],
                'currency': bid.token.currency
            })

        if token.minimal_bid:
            minimal_bid = token.minimal_bid / DECIMALS[token.currency]
        else:
            try:
                minimal_bid = ownership.minimal_bid / DECIMALS[token.currency]
            except:
                minimal_bid = None

        response_data = {
            'id': token.id,
            'name': token.name,
            'standart': token.standart,
            'media': token.media,
            'total_supply': token.total_supply,
            'available': available,
            'price': token.price / DECIMALS[token.currency] if token.price else None,
            'minimal_bid': minimal_bid,
            'currency': token.currency,
            'USD_price': calculate_amount(token.price, token.currency)[0] if token.price else None,
            'owners': token_owners,
            'history': token_history,
            'sellers': sellers_list,
            'creator': {
                    'id': token.creator.id,
                    'name': token.creator.get_name(),
                    'avatar': ALLOWED_HOSTS[0] + token.creator.avatar.url
                },
            'collection': {
                'id': token.collection.id,
                'avatar': collection_avatar,
                'name': token.collection.name,
                'address': token.collection.address
            },
            'bids': bid_list,
            'details': token.details,
            'royalty': token.creator_royalty,
            'selling': token.selling,
            'like_count': token.useraction_set.count(),
            'service_fee': service_fee,
            'internal_id': token.internal_id,
            'owner_auction': token.get_owner_auction()
        }
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
        responses={200: get_list_response},
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
        token_list = []
        length = tokens.count()

        start = (page - 1) * 50
        end = page * 50 if len(tokens) >= page * 50 else None
        
        for token in tokens[start:end]:
            collection_avatar = get_media_if_exists(token.collection, 'avatar')

            token_owners = []
            if token.standart == 'ERC1155':
                owners = token.owners.all()
                available = 0
                for owner in owners:
                    holder = {
                        'id': owner.id,
                        'name': owner.get_name(),
                        'avatar': get_media_if_exists(owner, 'avatar'),
                        'quantity': Ownership.objects.get(owner=owner, token=token).quantity
                        }
                    token_owners.append(holder)
                    if Ownership.objects.get(owner=owner, token=token).selling:
                        available += Ownership.objects.get(owner=owner, token=token).quantity
            else:
                owner = {
                    'id': token.owner.id,
                    'name': token.owner.get_name(),
                    'avatar': get_media_if_exists(token.owner, 'avatar'),
                    }
                token_owners.append(owner)
                if token.selling:
                    available = 1
                else:
                    available = 0

            try:
                highest_bid = Bid.objects.filter(state=Status.COMMITTED).filter(token=token).order_by(
                                            '-amount').first().amount
            except AttributeError:
                highest_bid = ''

            token_list.append({
                'id': token.id, 
                'name': token.name, 
                'standart': token.standart,
                'media': token.media, 
                'total_supply': token.total_supply,
                'available': available, 
                'price': (token.price / DECIMALS[token.currency] if token.price else None),
                'currency': token.currency, 
                'USD_price': (calculate_amount(token.price, token.currency)[0] if token.price else None),
                'owners': token_owners,
                'creator': {
                    'id': token.creator.id, 
                    'name': token.creator.get_name(), 
                    'avatar': ALLOWED_HOSTS[0] + token.creator.avatar.url
                },
                'collection': {
                    'id': token.collection.id,
                    'avatar': collection_avatar,
                    'name': token.collection.name
                },
                'details': token.details, 
                'royalty': token.creator_royalty, 
                'selling': token.selling,
                'service_fee': service_fee,
                'highest_bid': highest_bid / DECIMALS[token.currency] if highest_bid else None,
                'minimal_bid': token.minimal_bid / DECIMALS[token.currency] if token.minimal_bid else None

            })

        return Response({'tokens': token_list, 'length': length}, status=status.HTTP_200_OK)


class GetHotCollectionsView(APIView):
    '''
    View for getting hot collections
    '''

    @swagger_auto_schema(
        operation_description="get hot collections",
        responses={200: create_collection_response},
    )
    def get(self, request):
        collections = Collection.objects.exclude(name__in=('DDS-721', 'DDS-1155')).filter(Exists(Token.objects.filter(collection__id=OuterRef('id')))).order_by('-id')
        collection_list = []

        for collection in collections[:5]:
            media = get_media_if_exists(collection, 'avatar')

            tokens = Token.objects.exclude(status=Status.BURNED).filter(collection=collection).order_by(SORT_STATUSES['recent'])[:6]
            token_list = []

            for token in tokens:
                token_list.append(token.media)

            avatar = get_media_if_exists(collection.creator, 'avatar')

            creator_collections = {
                'id': collection.creator.id,
                'avatar': avatar,
                'name': collection.creator.get_name()
            }

            collection_list.append({
                'id': collection.id, 
                'name': collection.name, 
                'address': collection.address,
                'avatar': media, 
                'symbol': collection.symbol, 
                'description': collection.description,
                'creator': creator_collections, 
                'tokens': token_list
            })

        return Response(collection_list, status=status.HTTP_200_OK)

class GetCollectionView(APIView):
    '''
    View for get collection info in shop.
    '''
    @swagger_auto_schema(
        operation_description="get collection info",
        responses={200: get_collection_response, 400: 'collection not found'},
    )

    def get(self, request, id, page):
        try:
            collection = Collection.objects.get(id=id)
        except ObjectDoesNotExist:
            return Response({'error': 'collection not found'}, status=status.HTTP_400_BAD_REQUEST)

        token_list = []
        tokens = Token.objects.filter(collection=collection).exclude(status=Status.BURNED)

        start = (page - 1) * 50
        end = page * 50 if len(tokens) >= page * 50 else None

        avatar = get_media_if_exists(collection, 'avatar')

        cover = get_media_if_exists(collection, 'cover')

        for token in tokens[start: end]:
            token_owners = []
            if token.standart == 'ERC1155':
                owners = token.owners.all()
                available = 0
                for owner in owners:
                    holder = {
                        'id': owner.id,
                        'name': owner.get_name(),
                        'avatar': get_media_if_exists(owner, 'avatar'),
                        'quantity': Ownership.objects.get(owner=owner, token=token).quantity
                        }
                    token_owners.append(holder)
                    if Ownership.objects.get(owner=owner, token=token).selling:
                        available += Ownership.objects.get(owner=owner, token=token).quantity
            else:
                owner = {
                    'id': token.owner.id,
                    'name': token.owner.get_name(),
                    'avatar': get_media_if_exists(token.owner, 'avatar'),
                    }
                token_owners.append(owner)
                if token.selling:
                    available = 1
                else:
                    available = 0

            token_list.append({
                'id': token.id, 
                'name': token.name, 
                'standart': token.standart, 
                'media': token.media, 
                'total_supply': token.total_supply,
                'available': available, 
                'price': token.price / DECIMALS[token.currency] if token.price else None,
                'currency': token.currency,
                'USD_price': calculate_amount(token.price, token.currency)[0] if token.price else None,
                'owners': token_owners,
                'creator': {
                    'id': token.creator.id,
                    'name': token.creator.get_name(),
                    'avatar': ALLOWED_HOSTS[0] + token.creator.avatar.url
                },
                'collection': {
                    'id': token.collection.id,
                    'avatar': get_media_if_exists(token.collection, 'avatar'),
                    'name': token.collection.name
                },
                'description': token.description, 
                'details': token.details,
                'royalty': token.creator_royalty, 
                'selling': token.selling
            })

        response_data = {
            'id': collection.id, 
            'name': collection.name, 
            'avatar': avatar,
            'cover': cover,
            'creator': {
                'id': collection.creator.id,
                'name': collection.creator.get_name(),
                'avatar': get_media_if_exists(collection.creator, 'avatar')
                },
            'address': collection.address,
            'description': collection.description,
            'tokens': token_list
        }

        return Response(response_data, status=status.HTTP_200_OK)


class TransferOwned(APIView):
    '''
    View for tansfering token owned by user.
    '''

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
        #get token and collection
        id = request.data.get('id')
        new_owner = Web3.toChecksumAddress(request.data.get('address'))
        transferring_token = Token.objects.get(id=id)
        if transferring_token.status == Status.BURNED:
            return Response({'error': 'burned'}, status=status.HTTP_404_NOT_FOUND)
        if transferring_token.internal_id is None:
            return Response('token is not validated yet, please wait up to 5 minutes. If problem persists,'
                            'please contact us through support form', status=status.HTTP_400_BAD_REQUEST)
        #check user's authtoken
        try:
            token = AuthToken.objects.get(key=token)
            user = AdvUser.objects.get(id=token.user_id)
        except ObjectDoesNotExist:
            return Response({'error': 'user not found'}, status=status.HTTP_400_BAD_REQUEST)

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
    def post(self, request, token):
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

        try:
            token = AuthToken.objects.get(key=token)
            buyer = AdvUser.objects.get(id=token.user_id)
            if seller_id:
                seller = AdvUser.objects.get(id=seller_id)
                ownership = Ownership.objects.filter(token__id=token_id, owner=seller).filter(selling=True)
                if not ownership:
                    return Response({'error': 'user is not owner or token is not on sell'})
            else:
                seller = None
        except ObjectDoesNotExist:
            return Response({'error': 'user not found'}, status=status.HTTP_400_BAD_REQUEST)

        master_account = MasterUser.objects.get()

        if tradable_token.selling is False:
            return Response('token not selling', status=status.HTTP_403_FORBIDDEN)
        
        if tradable_token.standart == 'ERC721' and token_amount != 0:
            return Response('wrong token amount', status=status.HTTP_400_BAD_REQUEST)
            
        elif tradable_token.standart == 'ERC1155' and token_amount == 0:
            return Response('wrong token amount', status=status.HTTP_400_BAD_REQUEST) 
    
        buy = tradable_token.buy_token(token_amount, buyer, master_account, seller)

        return buy


@api_view(http_method_names=['GET'])
def get_tags(request):
    tag_list = []
    [tag_list.append(tag.name) for tag in Tags.objects.all()]
    return Response({'tags': tag_list}, status=status.HTTP_200_OK)


class MakeBid(APIView):
    '''
    view for making bid on auction
    '''

    @swagger_auto_schema(
        operation_description="make_bid",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'auth_token': openapi.Schema(type=openapi.TYPE_STRING),
                'token_id': openapi.Schema(type=openapi.TYPE_NUMBER),
                'amount': openapi.Schema(type=openapi.TYPE_NUMBER),
                'quantity': openapi.Schema(type=openapi.TYPE_NUMBER)
            }),
        responses={400:"you cant buy token"}
    )

    def post(self, request):
        request_data = request.data
        auth_token = request_data.get('auth_token')
        token_id = request_data.get('token_id')
        amount = request_data.get('amount')
        quantity = request_data.get('quantity')

        web3 = Web3(HTTPProvider(NETWORK_SETTINGS['ETH']['endpoint']))
        weth_contract = web3.eth.contract(
            address=web3.toChecksumAddress(WETH_CONTRACT['address']), abi=WETH_CONTRACT['abi'])

        try:
            user = AdvUser.objects.get(auth_token=auth_token)
        except:
            return Response({'error': 'User not found'}, status=status.HTTP_400_BAD_REQUEST)

        #returns True if OK, or error message
        result = validate_bid(user, token_id, amount, weth_contract, quantity)

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
                                                          web3.toChecksumAddress(EXCHANGE['address'])).call()
            user_balance = weth_contract.functions.balanceOf(Web3.toChecksumAddress(user.username)).call()
            if allowance < amount * quantity:
                tx_params = {
                    'chainId': web3.eth.chainId,
                    'gas': APPROVE_GAS_LIMIT,
                    'nonce': web3.eth.getTransactionCount(web3.toChecksumAddress(user.username), 'pending'),
                    'gasPrice': web3.eth.gasPrice,
                }
                initial_tx = weth_contract.functions.approve(web3.toChecksumAddress(EXCHANGE['address']), user_balance).buildTransaction(tx_params)
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
def get_bids(request, token_id, auth_token):
    #validating token and user
    try:
        token = Token.objects.get(id=token_id)
    except ObjectDoesNotExist:
        return Response({'error': 'token not found'}, status=status.HTTP_400_BAD_REQUEST)
    if not token.selling:
        return Response({'error': 'token is not on sale'}, status=status.HTTP_400_BAD_REQUEST)
    try:
        user = AdvUser.objects.get(auth_token=auth_token)
    except:
        return Response({'error': 'User not found'}, status=status.HTTP_400_BAD_REQUEST)
    if token.owner != user:
        return Response({'error': 'you can get bids list only for owned tokens'}, status=status.HTTP_400_BAD_REQUEST)

    bids = Bid.objects.filter(token=token)
    bid_list = []
    for bid in bids:
        bid_list.append({
            'id': bid.id,
            'bidder': bid.user.get_name(),
            'bidder_id': bid.user.id,
            'bidder_avatar': ALLOWED_HOSTS[0] + user.avatar.url,
            'quantity': bid.quantity,
            'amount': bid.amount / DECIMALS[bid.token.currency],
            'currency': bid.token.currency
            })

    return Response(bid_list, status=status.HTTP_200_OK)


class VerificateBetView(APIView):

    @swagger_auto_schema(
        operation_description="verificate bet",
        responses={200: 'ok', 400: 'verificate bet not found'},
    )
    def get(self, request, token_id):
        print('virificate!')
        web3 = Web3(HTTPProvider(NETWORK_SETTINGS['ETH']['endpoint']))
        weth_contract = web3.eth.contract(
            address=web3.toChecksumAddress(WETH_CONTRACT['address']),
            abi=WETH_CONTRACT['abi']
        )

        bets = Bid.objects.filter(token__id=token_id).order_by('-amount')
        max_bet = bets.first()
        if not max_bet:
            return Response(
                    {'invalid_bet': None, 'valid_bet': None},
                    status=status.HTTP_200_OK)
            
        user = max_bet.user
        amount = max_bet.amount
        quantity = max_bet.quantity

        check_valid = validate_bid(user, token_id, amount, weth_contract, quantity)

        if check_valid == 'OK':
            print('all ok!')
            return Response({
                'id':max_bet.id, 
                'amount': max_bet.amount, 
                'quantity': max_bet.quantity,
                'user': {
                    'id': user.id,
                    'name': user.display_name,
                    'address': user.username,
                    'avatar': get_media_if_exists(user, 'avatar')
                }
            }, status=status.HTTP_200_OK)
        
        else:
            print('not ok(')
            invalid_bet = {
                'id':max_bet.id, 
                'amount': max_bet.amount, 
                'quantity': max_bet.quantity,
                'user': {
                    'id': user.id,
                    'name': user.display_name,
                    'address': user.username,
                    'avatar': get_media_if_exists(user, 'avatar')
                }
            }
            max_bet.delete()
            for bet in bets:
                user = bet.user
                amount = bet.amount
                quantity = bet.quantity
                check_valid = validate_bid(user, token_id, amount, weth_contract, quantity)
                if check_valid == 'OK':
                    print('again ok!')
                    valid_bet = {
                            'id':bet.id, 
                            'amount': bet.amount, 
                            'quantity': bet.quantity,
                            'user': {
                                'id': user.id,
                                'name': user.display_name,
                                'address': user.username,
                                'avatar': get_media_if_exists(user, 'avatar')
                            }
                        }
                    return Response(
                        {
                            'invalid_bet': invalid_bet,
                            'valid_bet': valid_bet
                        }, 
                        status=status.HTTP_200_OK
                    )
                else:
                    bet.delete()
                    continue
            return Response(
                {'invalid_bet': invalid_bet, 'valid_bet': None},
                status=status.HTTP_200_OK)


class AuctionEndView(APIView):

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

        bets = Bid.objects.filter(token__id=token_id).order_by('-amount')
        bet = bets[0]

        master_account = MasterUser.objects.get()

        token = bet.token
        buyer = bet.user
        price = bet.amount

        seller_token = request.data.get('token')
        try:
            seller = AdvUser.objects.get(auth_token=seller_token)
            if token.standart == 'ERC721':
                if seller != token.owner:
                    return Response({'error': 'user is not owner or token is not on sell'})
            else:
                ownership = Ownership.objects.filter(token=token, owner=seller).first()
                if not ownership:
                    return Response({'error': 'user is not owner or token is not on sell'})
        except AdvUser.DoesNotExist:
            return Response({'error': not_found_response}, status=status.HTTP_401_UNAUTHORIZED)

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
                'message': openapi.Schema(type=openapi.TYPE_STRING)
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
    @swagger_auto_schema(
        operation_description='set cover',
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'id': openapi.Schema(type=openapi.TYPE_NUMBER),
                'auth_token': openapi.Schema(type=openapi.TYPE_STRING),
                'cover': openapi.Schema(type=openapi.TYPE_OBJECT)
            }
        ),
        responses={200: 'OK', 400: 'error'}
    )
    def post(self, request):
        auth_token = request.data.get('auth_token')
        collection_id = request.data.get('id')
        try:
            collection = Collection.objects.get(id=collection_id)
        except ObjectDoesNotExist:
            return Response({'error': 'collection not found'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            user = AdvUser.objects.get(auth_token=auth_token)
        except:
            return Response({'error': 'User not found'}, status=status.HTTP_400_BAD_REQUEST)
        if collection.creator != user:
            return Response({'error': 'you can set covers only for your collections'}, status=status.HTTP_400_BAD_REQUEST)
        collection.cover.save(request.FILES.get('cover').name, request.FILES.get('cover'))
        return Response(get_media_if_exists(collection, 'cover'), status=status.HTTP_200_OK)


@api_view(http_method_names=['GET'])
def get_fee(request):
    return Response(service_fee, status=status.HTTP_200_OK)


@api_view(http_method_names=['GET'])
def get_hot_bids(request):
    bids = Bid.objects.filter(state=Status.COMMITTED).order_by('-id')[:6]
    token_list= []
    for bid in bids:
        token = bid.token
        collection_avatar = get_media_if_exists(token.collection, 'avatar')
        token_owners = []
        if token.standart == 'ERC1155':
            available = 0
            owners = token.owners.all()
            for owner in owners[:3]:
                holder = {
                    'id': owner.id,
                    'name': owner.get_name(),
                    'avatar': get_media_if_exists(owner, 'avatar'),
                    'quantity': Ownership.objects.get(owner=owner, token=token).quantity
                }
            for owner in owners:
                if Ownership.objects.get(owner=owner, token=token).selling:
                    available += Ownership.objects.get(owner=owner, token=token).quantity
            try:
                token_owners.append(holder)
            except:
                pass
        else:
            owner = {
                'id': token.owner.id,
                'name': token.owner.get_name(),
                'avatar': get_media_if_exists(token.owner, 'avatar'),
            }
            token_owners.append(owner)
            if token.selling:
                available = 1
            else:
                available = 0

        highest_bid = Bid.objects.filter(state=Status.COMMITTED).filter(token=token).order_by(
                                         '-amount').first().amount

        token_list.append({
            'id': token.id,
            'name': token.name,
            'standart': token.standart,
            'media': token.media,
            'total_supply': token.total_supply,
            'available': available,
            'price': (token.price / DECIMALS[token.currency] if token.price else None),
            'currency': token.currency,
            'USD_price': (calculate_amount(token.price, token.currency)[0] if token.price else None),
            'owners': token_owners,
            'creator': {
                'id': token.creator.id,
                'name': token.creator.get_name(),
                'avatar': ALLOWED_HOSTS[0] + token.creator.avatar.url
            },
            'collection': {
                'id': token.collection.id,
                'avatar': collection_avatar,
                'name': token.collection.name
            },
            'details': token.details,
            'royalty': token.creator_royalty,
            'selling': token.selling,
            'service_fee': service_fee,
            'highest_bid': highest_bid / DECIMALS[token.currency]
        })
    return Response(token_list, status=status.HTTP_200_OK)


class SupportView(APIView):

    @swagger_auto_schema(
        operation_description='support view',
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'email': openapi.Schema(type=openapi.TYPE_STRING),
                'message': openapi.Schema(type=openapi.TYPE_STRING)
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
