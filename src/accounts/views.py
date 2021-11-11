import random

from src.store.api import get_email_connection
from src.accounts.models import AdvUser, VerificationForm
from src.accounts.serializers import (
    PatchSerializer, 
    MetamaskLoginSerializer, 
    UserSerializer, 
    UserSlimSerializer,
    SelfUserSerializer,
    FollowingSerializer,
    CoverSerializer,
)
from src.activity.models import UserAction
from src.settings import *
from src.store.models import Collection, Token
from src.store.serializers import UserCollectionSerializer
from src.store.services.ipfs import send_to_ipfs

from django.core.mail import send_mail 
from django.core.exceptions import ObjectDoesNotExist
from django.db import IntegrityError
from django.db.models import Q

from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema

from rest_auth.registration.views import SocialLoginView

from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView


not_found_response = 'user not found'


class MetamaskLogin(SocialLoginView):
    serializer_class = MetamaskLoginSerializer

    def login(self):

        self.user = self.serializer.validated_data['user']
        metamask_address = self.serializer.validated_data['address']

        try:
            user = AdvUser.objects.get(username__iexact=metamask_address)
        except ObjectDoesNotExist:
            print('try create user', flush=True)
            self.user = AdvUser(username=metamask_address, password=set_unusable_password())
            self.user.save()
            print('user_created', flush=True)

        return super().login()


class GetView(APIView):
    '''
    view for getting and patching user info
    '''
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="get self info",
        responses={200: SelfUserSerializer, 401: not_found_response},
    )
    def get(self, request):
        response_data = SelfUserSerializer(request.user).data
        return Response(response_data, status=status.HTTP_200_OK)

    @swagger_auto_schema(
        operation_description="update single user's info",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'display_name': openapi.Schema(type=openapi.TYPE_STRING),
                'avatar': openapi.Schema(type=openapi.TYPE_OBJECT),
                'bio': openapi.Schema(type=openapi.TYPE_STRING),
                'custom_url': openapi.Schema(type=openapi.TYPE_STRING),
                'twitter': openapi.Schema(type=openapi.TYPE_STRING),
                'instagram': openapi.Schema(type=openapi.TYPE_STRING),
                'facebook': openapi.Schema(type=openapi.TYPE_STRING),
                'site': openapi.Schema(type=openapi.TYPE_STRING)
            },
        ),
        responses={200: UserSlimSerializer, 400: 'attr: this attr is occupied', 401: not_found_response},
    )
    def patch(self, request):
        request_data = request.data.copy()
        user = request.user
        if request_data.get('custom_url')=='':
            request_data.pop('custom_url')
        
        serializer = PatchSerializer(user, data=request_data, partial=True)

        if serializer.is_valid():
            result = serializer.save()
        if serializer.errors:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
        #unique constraint handling:
        if isinstance(result, dict):
            return Response(result, status=status.HTTP_400_BAD_REQUEST)
        media = request.FILES.get('avatar')
        if media:
            ipfs = send_to_ipfs(media)
            user.avatar_ipfs = ipfs
            user.save()
        response_data = UserSlimSerializer(user).data
        return Response(response_data, status=status.HTTP_200_OK)


class GetOtherView(APIView):
    '''
    view for getting other user info
    '''

    @swagger_auto_schema(
        operation_description="get other user's info",
        responses={200: UserSerializer, 401: not_found_response},
    )
    def get(self, request, param):
        try:
            user = AdvUser.objects.get_by_custom_url(param)
        except ObjectDoesNotExist:
            return Response({'error': not_found_response}, status=status.HTTP_401_UNAUTHORIZED) 
        response_data = UserSerializer(user).data
        return Response(response_data, status=status.HTTP_200_OK)


class FollowView(APIView):
    '''
       View for following another user.
    '''
    permission_classes = [IsAuthenticated]
    @swagger_auto_schema(
        operation_description="follow user",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'id': openapi.Schema(type=openapi.TYPE_NUMBER),
            }),
        responses={200: 'OK', 400: 'error', 401: not_found_response}
    )

    def post(self, request):
        follower = request.user
        request_data = request.data
        id_ = request_data.get('id')

        try:
            user = AdvUser.objects.get_by_custom_url(id_)
        except ObjectDoesNotExist:
            return Response({'error': not_found_response}, status=status.HTTP_401_UNAUTHORIZED)

        if follower == user:
            return Response({'error': 'you cannot follow yourself'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            p = UserAction.objects.create(user=follower, whom_follow=user)
        except IntegrityError:
            return Response({'error': 'already following'}, status=status.HTTP_400_BAD_REQUEST)

        return Response('Followed', status=status.HTTP_200_OK)


class UnfollowView(APIView):
    '''
       View for unfollowing another user.
    '''
    permission_classes = [IsAuthenticated]
    @swagger_auto_schema(
        operation_description="unfollow user",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'id': openapi.Schema(type=openapi.TYPE_NUMBER),
            }),
        responses={200: 'OK', 400: 'error', 401: not_found_response}
    )

    def post(self, request):
        follower = request.user
        request_data = request.data
        id_ = request_data.get('id')
        
        try:
            user = AdvUser.objects.get_by_custom_url(id_)
        except ObjectDoesNotExist:
            return Response({'error': not_found_response}, status=status.HTTP_401_UNAUTHORIZED) 
        
        link = UserAction.objects.filter(whom_follow=user, user=follower)
        
        if link:
            link[0].delete()
            return Response('OK', status=status.HTTP_200_OK)
        else:
            return Response({'error': 'nothing to unfollow'}, status=status.HTTP_400_BAD_REQUEST)


class LikeView(APIView):
    '''
       View for liking token.
    '''
    permission_classes = [IsAuthenticated]
    @swagger_auto_schema(
        operation_description="like token",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'id': openapi.Schema(type=openapi.TYPE_NUMBER),
            }),
        responses={200: 'liked/unliked', 400: 'error', 401: not_found_response}
    )

    def post(self, request):
        request_data = request.data
        token_id = request_data.get('id')

        try:
            item = Token.objects.committed().get(id=token_id)
        except ObjectDoesNotExist:
            return Response({'error': 'nothing to like'}, status=status.HTTP_400_BAD_REQUEST) 

        like, created = UserAction.objects.get_or_create(
            user=request.user, 
            whom_follow=None, 
            method='like', 
            token=item
        )
           
        if created is False:
            like.delete()
            return Response('unliked', status=status.HTTP_200_OK)

        return Response('liked', status=status.HTTP_200_OK)

  
class GetUserCollections(APIView):
    '''
    View for get collections by user
    '''
    permission_classes = [IsAuthenticated]
    @swagger_auto_schema(
        operation_description="get collections by user",
        manual_parameters=[
            openapi.Parameter("network", openapi.IN_QUERY, type=openapi.TYPE_STRING),
        ],
        resposnes={200: UserCollectionSerializer, 401: not_found_response}
    )
    def get(self, request):
        network = request.query_params.get('network', config.DEFAULT_NETWORK)
        collections = Collection.objects.committed().user_collections(request.user, network=network)
        response_data = UserCollectionSerializer(collections, many=True).data
        return Response({'collections': response_data}, status=status.HTTP_200_OK)


class GetFollowingView(APIView):
    '''
    View for getting active tokens of following users
    '''
    @swagger_auto_schema(
        operation_description="post search pattern",
        responses={200: FollowingSerializer(many=True), 401: not_found_response},
    )

    def get(self, request, address, page):
        try:
            user = AdvUser.objects.get_by_custom_url(address)
        except ObjectDoesNotExist:
            return Response({'error': not_found_response}, status=status.HTTP_401_UNAUTHORIZED)

        follow_queryset = UserAction.objects.filter(method='follow', user=user)
        followed_users = [action.whom_follow for action in follow_queryset]
        response_data = FollowingSerializer(followed_users, many=True).data
        return Response(response_data, status=status.HTTP_200_OK)


class GetFollowersView(APIView):
    '''
    View for getting active tokens of following users
    '''
    @swagger_auto_schema(
        operation_description="post search pattern",
        responses={200: FollowingSerializer(many=True), 401: not_found_response},
    )

    def get(self, request, address, page):
        try:
            user = AdvUser.objects.get_by_custom_url(address)
        except ObjectDoesNotExist:
            return Response({'error': not_found_response}, status=status.HTTP_401_UNAUTHORIZED)

        follow_queryset = UserAction.objects.filter(method='follow', whom_follow=user)
        followers_users = [action.user for action in follow_queryset]
        response_data = FollowingSerializer(followers_users, many=True).data
        return Response(response_data, status=status.HTTP_200_OK)


class VerificationView(APIView):
    '''
       View for liking token.
    '''
    permission_classes = [IsAuthenticated]
    @swagger_auto_schema(
        operation_description="like token",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'url': openapi.Schema(type=openapi.TYPE_STRING),
                'address': openapi.Schema(type=openapi.TYPE_STRING),
                'role': openapi.Schema(type=openapi.TYPE_STRING),
                'bio': openapi.Schema(type=openapi.TYPE_STRING),
                'twitter': openapi.Schema(type=openapi.TYPE_STRING),
                'media': openapi.Schema(type=openapi.TYPE_STRING),
                'instagram': openapi.Schema(type=openapi.TYPE_STRING),
                'website': openapi.Schema(type=openapi.TYPE_STRING),
                'email': openapi.Schema(type=openapi.TYPE_STRING)
            },
            required = ['bio', 'email']),
        responses={200: 'Verification request sent', 400: 'Form already sent', 401: not_found_response}
    )

    def post(self, request):
        user = request.user
        verification = VerificationForm(user=user)
        try:
            verification.save()
        except IntegrityError:
            return Response({'error': 'Request already sent'}, status=status.HTTP_400_BAD_REQUEST)
        verification.save_form(request)

        connection = get_email_connection()
        text = """
                        New veridication request arrived!
                        URL: https://{domain}/django-admin/accounts/advuser/{id}/change/
                        """.format(domain=ALLOWED_HOSTS[0], id=user.id)

        send_mail(
            'New verification request',
            text,
            config.HOST_USER,
            [config.MAIL],
            connection=connection,
        )
        print('message sent')

        return Response('Verification request sent', status=status.HTTP_200_OK)


class SetUserCoverView(APIView):
    permission_classes = [IsAuthenticated]
    @swagger_auto_schema(
        operation_description='set cover',
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'cover': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    format=openapi.FORMAT_BINARY
            ),
            }
        ),
        responses={200: 'OK', 400: 'error'}
    )
    def post(self, request):
        user = request.user
        media = request.FILES.get('cover')
        if media:
            ipfs = send_to_ipfs(media)
            user.cover_ipfs = ipfs
            user.save()
        return Response(user.cover, status=status.HTTP_200_OK)


class GetRandomCoverView(APIView):
    @swagger_auto_schema(
        operation_description='get random cover',
        responses={200: CoverSerializer, 400: 'error'}
    )
    def get(self, request):
        #covers = AdvUser.objects.exclude(cover=None).exclude(cover='').exclude(is_verificated=False)
        covers = AdvUser.objects.exclude(cover_ipfs=None).exclude(cover_ipfs='').exclude(is_verificated=False)
        try:
            random_cover = random.choice(covers)
        except:
            return Response({'error': 'there is no available cover'}, status=status.HTTP_404_NOT_FOUND)
        response_data = CoverSerializer(random_cover).data
        return Response(response_data, status=status.HTTP_200_OK)