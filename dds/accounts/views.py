import random

from dds.store.api import get_dds_email_connection
from dds.accounts.api import follow_and_follower, valid_metamask_message
from dds.accounts.models import AdvUser, VerificationForm
from dds.accounts.serializers import PatchSerializer
from dds.activity.models import UserAction
from dds.settings import *
from dds.store.models import Collection, Token
from dds.utilities import get_media_if_exists

from django.core.mail import send_mail 
from django.contrib.auth import login, logout
from django.core.exceptions import ObjectDoesNotExist
from django.db import IntegrityError

from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema

from rest_auth.registration.serializers import SocialLoginSerializer
from rest_auth.registration.views import SocialLoginView

from rest_framework import serializers, status
from rest_framework.authtoken.models import Token as AuthToken
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

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

get_list_response = openapi.Response(
    description='Response with search results',
    schema=openapi.Schema(
        type=openapi.TYPE_ARRAY,
        items=openapi.Items(type=openapi.TYPE_OBJECT,
        properties={
            'id': openapi.Schema(type=openapi.TYPE_NUMBER),
            'name': openapi.Schema(type=openapi.TYPE_STRING),
            'avatar': openapi.Schema(type=openapi.TYPE_STRING),
            'following counnt': openapi.Schema(type=openapi.TYPE_NUMBER),
            'token': openapi.Schema(type=openapi.TYPE_OBJECT)
        }
    ))
)

random_cover_response = openapi.Response(
    description='Response with random cover',
    schema=openapi.Schema(
        type=openapi.TYPE_ARRAY,
        items=openapi.Items(type=openapi.TYPE_OBJECT,
        properties={
            'id': openapi.Schema(type=openapi.TYPE_NUMBER),
            'name': openapi.Schema(type=openapi.TYPE_STRING),
            'avatar': openapi.Schema(type=openapi.TYPE_STRING),
            'cover': openapi.Schema(type=openapi.TYPE_STRING),
        }
    ))
)

not_found_response = 'user not found'


class MetamaskLoginSerializer(SocialLoginSerializer):
    address = serializers.CharField(required=False, allow_blank=True)
    msg = serializers.CharField(required=False, allow_blank=True)
    signed_msg = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        address = attrs['address']
        signature = attrs['signed_msg']
        session = self.context['request'].session
        message = session.get('metamask_message')

        if message is None:
            message = attrs['msg']

        print('metamask login, address', address, 'message', message, 'signature', signature, flush=True)
        if valid_metamask_message(address, message, signature):
            metamask_user = AdvUser.objects.filter(username__iexact=address).first()

            if metamask_user is None:
                self.user = AdvUser.objects.create_user(username=address)
            else:
                self.user = metamask_user

            attrs['user'] = self.user

            if not self.user.is_active:
                raise PermissionDenied(1035)
            
        else:
            raise PermissionDenied(1034)

        return attrs


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

    @swagger_auto_schema(
        operation_description="get self info",
        responses={200: get_response, 401: not_found_response},
    )
    def get(self, request, token):
        try:
            user = AdvUser.objects.get(auth_token=token)
        except ObjectDoesNotExist:
            return Response({'error': not_found_response}, status=status.HTTP_401_UNAUTHORIZED)

        follows, followers = follow_and_follower(user)

        likes_action = UserAction.objects.filter(method='like', user=user)
        likes = [action.token.id for action in likes_action]
       
        response_data = {
            'id': user.id, 
            'address': user.username, 
            'display_name': user.display_name, 
            'avatar': ALLOWED_HOSTS[0] + user.avatar.url,
            'cover': get_media_if_exists(user, 'cover'),
            'custom_url': user.custom_url, 
            'bio': user.bio, 
            'twitter': user.twitter,
            'instagram': user.instagram,
            'site': user.site,
            'is_verificated': user.is_verificated, 
            'follows': follows,
            'follows_count': len(follows),
            'followers': followers,
            'followers_count': len(followers),
            'likes': likes
        }

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
                'site': openapi.Schema(type=openapi.TYPE_STRING)
            },
        ),
        responses={200: get_response, 400: 'attr: this attr is occupied', 401: not_found_response},
    )
    def patch(self, request, token):
        request_data = request.data.copy()
        try:
            user = AdvUser.objects.get(auth_token=token)
        except ObjectDoesNotExist:
            return Response({'error': not_found_response}, status=status.HTTP_401_UNAUTHORIZED)
        if request_data.get('custom_url')=='':
            request_data.pop('custom_url')
        if request_data.get('twitter')=='':
            request_data.pop('twitter')
        if request_data.get('instagram')=='':
            request_data.pop('instagram')
        if request_data.get('site')=='':
            request_data.pop('site')
        if request_data.get('displey_name')=='':
            request_data.pop('display_name')
        

        serializer = PatchSerializer(user, data=request_data, partial=True)

        if serializer.is_valid():
            result = serializer.save()
            
        #unique constraint handling:
        if isinstance(result, dict):
            return Response(result, status=status.HTTP_400_BAD_REQUEST)

        response_data = {
            'id': user.id, 
            'address': user.username, 
            'display_name': user.display_name, 
            'avatar': ALLOWED_HOSTS[0] + user.avatar.url,
            'custom_url': user.custom_url, 
            'bio': user.bio, 
            'twitter': user.twitter, 
            'instagram': user.instagram,
            'site': user.site,
            'is_verificated': user.is_verificated}

        return Response(response_data, status=status.HTTP_200_OK)


class GetOtherView(APIView):
    '''
    view for getting other user info
    '''

    @swagger_auto_schema(
        operation_description="get other user's info",
        responses={200: get_response, 401: not_found_response},
    )
    def get(self, request, id):
        try:
            user = AdvUser.objects.get(id=id)
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
            'instagram': user.instagram,
            'site': user.site,
            'is_verificated': user.is_verificated,
            'follows': follows,
            'follows_count': len(follows),
            'followers': followers,
            'followers_count': len(followers),
        }

        return Response(response_data, status=status.HTTP_200_OK)


class FollowView(APIView):
    '''
       View for following another user.
    '''

    @swagger_auto_schema(
        operation_description="follow user",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'id': openapi.Schema(type=openapi.TYPE_NUMBER),
            }),
        responses={200: 'OK', 400: 'error', 401: not_found_response}
    )

    def post(self, request, token):
        try:
            follower = AdvUser.objects.get(auth_token=token)
        except ObjectDoesNotExist:
            return Response({'error': not_found_response}, status=status.HTTP_401_UNAUTHORIZED)

        request_data = request.data
        id = request_data.get('id')

        try:
            follow = AdvUser.objects.get(id=id)
        except ObjectDoesNotExist:
            return Response({'error': not_found_response}, status=status.HTTP_401_UNAUTHORIZED)

        if follower == follow:
            return Response({'error': 'you cannot follow yourself'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            p = UserAction.objects.create(user=follower, whom_follow=follow)
        except IntegrityError:
            return Response({'error': 'already following'}, status=status.HTTP_400_BAD_REQUEST)

        return Response('Followed', status=status.HTTP_200_OK)


class UnfollowView(APIView):
    '''
       View for unfollowing another user.
    '''

    @swagger_auto_schema(
        operation_description="unfollow user",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'id': openapi.Schema(type=openapi.TYPE_NUMBER),
            }),
        responses={200: 'OK', 400: 'error', 401: not_found_response}
    )

    def post(self, request, token):
        try:
            follower = AdvUser.objects.get(auth_token=token)
        except ObjectDoesNotExist:
            return Response({'error': not_found_response}, status=status.HTTP_401_UNAUTHORIZED)
        
        request_data = request.data
        id = request_data.get('id')
        
        try:
            follow = AdvUser.objects.get(id=id)
        except ObjectDoesNotExist:
            return Response({'error': not_found_response}, status=status.HTTP_401_UNAUTHORIZED)
        
        link = UserAction.objects.filter(whom_follow=follow, user=follower)
        
        if link:
            link[0].delete()
            return Response('OK', status=status.HTTP_200_OK)
        else:
            return Response({'error': 'nothing to unfollow'}, status=status.HTTP_400_BAD_REQUEST)


class LikeView(APIView):
    '''
       View for liking token.
    '''

    @swagger_auto_schema(
        operation_description="like token",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'id': openapi.Schema(type=openapi.TYPE_NUMBER),
            }),
        responses={200: 'liked/unliked', 400: 'error', 401: not_found_response}
    )

    def post(self, request, token):
        try:
            follower = AdvUser.objects.get(auth_token=token)
        except ObjectDoesNotExist:
            return Response({'error': not_found_response}, status=status.HTTP_401_UNAUTHORIZED)

        request_data = request.data
        token_id = request_data.get('id')

        try:
            item = Token.objects.get(id=token_id)
        except ObjectDoesNotExist:
            return Response({'error': 'nothing to like'}, status=status.HTTP_400_BAD_REQUEST)


        like, created = UserAction.objects.get_or_create(
            user=follower, 
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

    @swagger_auto_schema(
        operation_description="get collections by user",
        resposnes={200: get_response, 401: not_found_response}
    )
    def get(self, request, string):
        try:
            if string[:2] == '0x':
                user = AdvUser.objects.get(username=string)
            else:
                user = AdvUser.objects.get(auth_token=string)

        except:
            return Response({'error': 'user not found'}, status=status.HTTP_400_BAD_REQUEST)

        collections = Collection.objects.filter(name__in=('DDS-721', 'DDS-1155')).filter(status__iexact='Committed')
        collections |= Collection.objects.filter(creator=user).filter(status__iexact='Committed')
        collection_list = []

        for collection in collections:
            token_list = []
            for token in collection.token_set.all()[:6]:
                token_media = get_media_if_exists(token, 'media')
                token_list.append(token_media)

            avatar = get_media_if_exists(collection, 'avatar')
            collection_list.append({
                'id': collection.id,
                'name':collection.name,
                'avatar':avatar,
                'address':collection.address,
                'symbol':collection.symbol,
                'description':collection.description,
                'standart':collection.standart,
                'short_url':collection.short_url,
                'creator':collection.creator.username,
                'status':collection.status,
                'deploy_hash':collection.deploy_hash,
                'deploy_block':collection.deploy_block,
                'tokens': token_list
            })
        
        return Response({'collections': collection_list}, status=status.HTTP_200_OK)


class GetFollowingView(APIView):
    '''
    View for getting active tokens of following users
    '''
    @swagger_auto_schema(
        operation_description="post search pattern",
        responses={200: get_list_response, 401: not_found_response},
    )

    def get(self, request, address, page):
        try:
            user = AdvUser.objects.get(username=address)
        except ObjectDoesNotExist:
            return Response({'error': not_found_response}, status=status.HTTP_401_UNAUTHORIZED)

        follow_queryset = UserAction.objects.filter(method='follow', user=user)
        followed_users = [action.whom_follow for action in follow_queryset]
        
        result_list = []

        for person in followed_users:
            # the number of subscribers of the person we follow
            followers_count = len(
                UserAction.objects.filter(method='follow', whom_follow=person)
            )

            person_tokens = []
            for token in person.token_owner.all()[:5]:
                token_info = {
                    'id': token.id,
                    'media': get_media_if_exists(token, 'media')
                }

                person_tokens.append(token_info)

            person_info = {
                'id': person.id,
                'avatar': get_media_if_exists(person, 'avatar'),
                'name': person.get_name(),
                'followers_count': followers_count,
                'tokens': person_tokens
            }

            result_list.append(person_info)
        return Response(result_list, status=status.HTTP_200_OK)


class GetFollowersView(APIView):
    '''
    View for getting active tokens of following users
    '''
    @swagger_auto_schema(
        operation_description="post search pattern",
        responses={200: get_list_response, 401: not_found_response},
    )

    def get(self, request, address, page):
        try:
            user = AdvUser.objects.get(username=address)
        except ObjectDoesNotExist:
            return Response({'error': not_found_response}, status=status.HTTP_401_UNAUTHORIZED)

        follow_queryset = UserAction.objects.filter(method='follow', whom_follow=user)
        followers_users = [action.user for action in follow_queryset]

        result_list = []

        for person in followers_users:
            
            followers_count = len(
                UserAction.objects.filter(method='follow', whom_follow=person)
            )

            person_tokens = []
            for token in person.token_owner.all()[:5]:
                token_info = {
                    'id': token.id,
                    'media': get_media_if_exists(token, 'media')
                }

                person_tokens.append(token_info)

            person_info = {
                'id': person.id,
                'avatar': get_media_if_exists(person, 'avatar'),
                'name': person.get_name(),
                'followers_count': followers_count,
                'tokens': person_tokens
            }

            result_list.append(person_info)

        return Response(result_list, status=status.HTTP_200_OK)


class VerificationView(APIView):
    '''
       View for liking token.
    '''

    @swagger_auto_schema(
        operation_description="like token",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'auth_token': openapi.Schema(type=openapi.TYPE_STRING),
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
        auth_token = request.data.get('auth_token')
        try:
            user = AdvUser.objects.get(auth_token=auth_token)
        except ObjectDoesNotExist:
            return Response({'error': not_found_response}, status=status.HTTP_401_UNAUTHORIZED)

        verification = VerificationForm(user=user)
        try:
            verification.save()
        except IntegrityError:
            return Response({'error': 'Request already sent'}, status=status.HTTP_400_BAD_REQUEST)
        verification.save_form(request)

        connection = get_dds_email_connection()
        text = """
                        New veridication request arrived!
                        URL: https://{domain}/django-admin/accounts/advuser/{id}/change/
                        """.format(domain=ALLOWED_HOSTS[0], id=user.id)

        send_mail(
            'New verification request',
            text,
            DDS_HOST_USER,
            [DDS_MAIL],
            connection=connection,
        )
        print('message sent')

        return Response('Verification request sent', status=status.HTTP_200_OK)


class SetUserCoverView(APIView):
    @swagger_auto_schema(
        operation_description='set cover',
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'auth_token': openapi.Schema(type=openapi.TYPE_STRING),
                'cover': openapi.Schema(type=openapi.TYPE_OBJECT)
            }
        ),
        responses={200: 'OK', 400: 'error'}
    )
    def post(self, request):
        auth_token = request.data.get('auth_token')
        try:
            user = AdvUser.objects.get(auth_token=auth_token)
        except:
            return Response({'error': 'User not found'}, status=status.HTTP_400_BAD_REQUEST)
        user.cover.save(request.FILES.get('cover').name, request.FILES.get('cover'))
        return Response(get_media_if_exists(user, 'cover'), status=status.HTTP_200_OK)


class GetRandomCoverView(APIView):
    @swagger_auto_schema(
        operation_description='get random cover',
        responses={200: random_cover_response, 400: 'error'}
    )
    def get(self, request):
        covers = AdvUser.objects.exclude(cover=None).exclude(cover='').exclude(is_verificated=False)
        try:
            random_cover = random.choice(covers)
        except:
            return Response({'error': 'there is no available cover'}, status=status.HTTP_404_NOT_FOUND)
        response_data = {
            'cover': get_media_if_exists(random_cover, 'cover'), 'owner': random_cover.get_name(),
            'avatar': get_media_if_exists(random_cover, 'avatar'), 'id': random_cover.id
            }
        return Response(response_data, status=status.HTTP_200_OK)
