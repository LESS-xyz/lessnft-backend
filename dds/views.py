from rest_framework.response import Response
from rest_framework import status
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework.views import APIView
from django.core.exceptions import ObjectDoesNotExist

from dds.store.models import Collection, Token
from dds.store.serializers import CollectionSerializer
from dds.accounts.models import AdvUser
from dds.accounts.serializers import UserSerializer

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

        tokens = Token.objects.filter(collection=collection)

        start = (page - 1) * 50
        end = page * 50 if len(tokens) >= page * 50 else None

        token_list = tokens[start:end]
        response_data = CollectionSerializer(collection, context={"tokens": token_list}).data
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
        response_data = UserSerializer(user).data
        return Response(response_data, status=status.HTTP_200_OK)