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


not_found_response = 'user not found'


class GetShortView(APIView):
    '''
    View for getting collection by a short_url
    '''

    @swagger_auto_schema(
        operation_description="get collection info",
        responses={200: CollectionSerializer, 400: 'collection not found'},
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
        responses={200: UserSerializer, 401: not_found_response},
    )
    def get(self, request, short):
        try:
            user = AdvUser.objects.get(custom_url=short)
        except ObjectDoesNotExist:
            return Response({'error': not_found_response}, status=status.HTTP_401_UNAUTHORIZED)
        response_data = UserSerializer(user).data
        return Response(response_data, status=status.HTTP_200_OK)