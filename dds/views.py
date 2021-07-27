from rest_framework.response import Response
from rest_framework import status
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework.request import Request
from rest_framework.views import APIView
from django.core.exceptions import ObjectDoesNotExist

from dds.store.models import Collection, Token, Ownership
from dds.accounts.models import AdvUser
from dds.accounts.api import follow_and_follower
from dds.utilities import get_media_if_exists
from dds.settings import ALLOWED_HOSTS
from dds.consts import DECIMALS

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

get_response = openapi.Response(
    description="Response with user info",
    schema=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'id': openapi.Schema(type=openapi.TYPE_NUMBER),
            'address': openapi.Schema(type=openapi.TYPE_STRING),
            'display_name': openapi.Schema(type=openapi.TYPE_STRING),
            'avatar': openapi.Schema(type=openapi.TYPE_STRING),
            'bio': openapi.Schema(type=openapi.TYPE_STRING),
            'custom_url': openapi.Schema(type=openapi.TYPE_STRING),
            'twitter': openapi.Schema(type=openapi.TYPE_STRING),
            'site': openapi.Schema(type=openapi.TYPE_STRING),
            'follows': openapi.Schema(type=openapi.TYPE_OBJECT),
            'followers': openapi.Schema(type=openapi.TYPE_OBJECT)
        }
    )
)

not_found_response = 'user not found'


class GetShortView(APIView):
    '''
    View for getting collection by a short_url
    '''

    @swagger_auto_schema(
        operation_description="get collection info",
        responses={200: get_collection_response, 400: 'collection not found'},
    )
    def get(self, request, short, page):
        try:
            collection = Collection.objects.get(short_url=short)
        except ObjectDoesNotExist:
            return Response({'error': 'collection not found'}, status=status.HTTP_400_BAD_REQUEST)

        token_list = []
        tokens = Token.objects.filter(collection=collection)

        start = (page - 1) * 50
        end = page * 50 if len(tokens) >= page * 50 else None

        avatar = get_media_if_exists(collection, 'avatar')

        cover = get_media_if_exists(collection, 'cover')

        for token in tokens[start: end]:
            media = get_media_if_exists(token, 'media')

            token_owners = []
            if token.standart == 'ERC1155':
                owners = token.owners.all()
                for owner in owners[:3]:
                    holder = {
                        'id': owner.id,
                        'name': owner.get_name(),
                        'avatar': get_media_if_exists(owner, 'avatar'),
                        'quantity': Ownership.objects.get(owner=owner, token=token).quantity
                    }
                    token_owners.append(holder)
            else:
                owner = {
                    'id': token.owner.id,
                    'name': token.owner.get_name(),
                    'avatar': get_media_if_exists(token.owner, 'avatar'),
                }
                token_owners.append(owner)

            token_list.append({
                'id': token.id,
                'name': token.name,
                'standart': token.standart,
                'media': media,
                'total_supply': token.total_supply,
                'available': token.available,
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
                    'avatar': ALLOWED_HOSTS[0] + token.collection.avatar.url,
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

class GetShortUserView(APIView):
    '''
    view for getting user info by short_url
    '''

    @swagger_auto_schema(
        operation_description="get other user's info",
        responses={200: get_response, 401: not_found_response},
    )
    def get(self, request, short):
        try:
            user = AdvUser.objects.get(custom_url=short)
        except ObjectDoesNotExist:
            return Response({'error': not_found_response}, status=status.HTTP_401_UNAUTHORIZED)

        follows, followers = follow_and_follower(user)

        response_data = {
            'id': user.id,
            'address': user.username,
            'display_name': user.display_name,
            'avatar': ALLOWED_HOSTS[0] + user.avatar.url,
            'cover': get_media_if_exists(user, 'cover'),
            'custom_url': user.custom_url,
            'bio': user.bio,
            'twitter': user.twitter,
            'site': user.site,
            'is_verificated': user.is_verificated,
            'follows': follows,
            'follows_count': len(follows),
            'followers': followers,
            'followers_count': len(followers),
        }
        print('res:', response_data)

        return Response(response_data, status=status.HTTP_200_OK)