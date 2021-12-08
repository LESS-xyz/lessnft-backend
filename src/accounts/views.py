import random

from src.utilities import PaginateMixin

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
from src.settings import config, ALLOWED_HOSTS
from src.store.models import Collection, Token
from src.store.serializers import UserCollectionSerializer
from src.store.services.ipfs import send_to_ipfs

from django.core.mail import send_mail
from django.core.exceptions import ObjectDoesNotExist
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema

from rest_auth.registration.views import SocialLoginView

from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView


not_found_response = "user not found"


class MetamaskLogin(SocialLoginView):
    serializer_class = MetamaskLoginSerializer

    def login(self):
        self.user = self.serializer.validated_data["user"]
        return super().login()


class GetView(APIView):
    """
    view for getting and patching user info
    """

    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="get self info",
        responses={200: SelfUserSerializer},
    )
    def get(self, request):
        response_data = SelfUserSerializer(request.user).data
        return Response(response_data, status=status.HTTP_200_OK)

    @swagger_auto_schema(
        operation_description="Update current user info",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "display_name": openapi.Schema(type=openapi.TYPE_STRING),
                "avatar": openapi.Schema(type=openapi.TYPE_OBJECT),
                "bio": openapi.Schema(type=openapi.TYPE_STRING),
                "custom_url": openapi.Schema(type=openapi.TYPE_STRING),
                "twitter": openapi.Schema(type=openapi.TYPE_STRING),
                "instagram": openapi.Schema(type=openapi.TYPE_STRING),
                "facebook": openapi.Schema(type=openapi.TYPE_STRING),
                "site": openapi.Schema(type=openapi.TYPE_STRING),
            },
        ),
        responses={200: UserSlimSerializer, 400: "attr: this attr is occupied"},
    )
    def patch(self, request):
        request_data = request.data.copy()
        user = request.user
        if request_data.get("custom_url") == "":
            request_data.pop("custom_url")

        serializer = PatchSerializer(user, data=request_data, partial=True)

        if serializer.is_valid():
            result = serializer.save()
        if serializer.errors:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # unique constraint handling:
        if isinstance(result, dict):
            return Response(result, status=status.HTTP_400_BAD_REQUEST)
        media = request.FILES.get("avatar")
        if media:
            ipfs = send_to_ipfs(media)
            user.avatar_ipfs = ipfs
            user.save()
        response_data = UserSlimSerializer(user).data
        return Response(response_data, status=status.HTTP_200_OK)


class GetOtherView(APIView):
    """
    view for getting other user info
    """

    @swagger_auto_schema(
        operation_description="get other user's info",
        responses={200: UserSerializer},
    )
    def get(self, request, param):
        try:
            user = AdvUser.objects.get_by_custom_url(param)
        except ObjectDoesNotExist:
            return Response(
                {"error": "User not found"}, status=status.HTTP_404_NOT_FOUND
            )
        response_data = UserSerializer(user).data
        return Response(response_data, status=status.HTTP_200_OK)


class FollowView(APIView):
    """
    View for following another user.
    """

    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="follow user",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "id": openapi.Schema(type=openapi.TYPE_NUMBER),
            },
        ),
        responses={200: "OK", 400: "error"},
    )
    def post(self, request):
        follower = request.user
        request_data = request.data
        id_ = request_data.get("id")

        try:
            user = AdvUser.objects.get_by_custom_url(id_)
        except ObjectDoesNotExist:
            return Response(
                {"error": not_found_response}, status=status.HTTP_404_NOT_FOUND
            )

        if follower == user:
            return Response(
                {"error": "you cannot follow yourself"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        UserAction.objects.get_or_create(user=follower, whom_follow=user)
        return Response("Followed", status=status.HTTP_200_OK)


class UnfollowView(APIView):
    """
    View for unfollowing another user.
    """

    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="unfollow user",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "id": openapi.Schema(type=openapi.TYPE_NUMBER),
            },
        ),
        responses={200: "OK", 404: "User not found"},
    )
    def post(self, request):
        follower = request.user
        request_data = request.data
        id_ = request_data.get("id")

        try:
            user = AdvUser.objects.get_by_custom_url(id_)
        except ObjectDoesNotExist:
            return Response(
                {"error": "User not found"}, status=status.HTTP_404_NOT_FOUND
            )

        UserAction.objects.filter(whom_follow=user, user=follower).delete()
        return Response("OK", status=status.HTTP_200_OK)


class LikeView(APIView):
    """
    View for liking token.
    """

    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="like token",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "id": openapi.Schema(type=openapi.TYPE_NUMBER),
            },
        ),
        responses={200: "liked/unliked", 404: "Token not found"},
    )
    def post(self, request):
        request_data = request.data
        token_id = request_data.get("id")

        try:
            item = Token.objects.committed().get(id=token_id)
        except ObjectDoesNotExist:
            return Response(
                {"error": "Token not found"}, status=status.HTTP_404_NOT_FOUND
            )

        like, created = UserAction.objects.get_or_create(
            user=request.user, whom_follow=None, method="like", token=item
        )

        if created is False:
            like.delete()
            return Response("unliked", status=status.HTTP_200_OK)
        return Response("liked", status=status.HTTP_200_OK)


class GetUserCollections(APIView, PaginateMixin):
    """
    View for get collections by user
    """

    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="get collections by user",
        manual_parameters=[
            openapi.Parameter("network", openapi.IN_QUERY, type=openapi.TYPE_STRING),
        ],
        resposnes={200: UserCollectionSerializer},
    )
    def get(self, request):
        network = request.query_params.get("network", config.DEFAULT_NETWORK)
        collections = Collection.objects.committed().user_collections(
            request.user, network=network
        )
        collections = UserCollectionSerializer(collections, many=True).data
        return Response(self.paginate(request, collections), status=status.HTTP_200_OK)


class GetFollowingView(APIView, PaginateMixin):
    """
    View for getting active tokens of following users
    """

    @swagger_auto_schema(
        operation_description="post search pattern",
        responses={200: FollowingSerializer(many=True), 404: "User not found"},
    )
    def get(self, request, address):
        try:
            user = AdvUser.objects.get_by_custom_url(address)
        except ObjectDoesNotExist:
            return Response(
                {"error": "User not found"}, status=status.HTTP_404_NOT_FOUND
            )

        follow_queryset = UserAction.objects.filter(method="follow", user=user)
        followed_users = [action.whom_follow for action in follow_queryset]
        users = FollowingSerializer(followed_users, many=True).data
        return Response(self.paginate(request, users), status=status.HTTP_200_OK)


class GetFollowersView(APIView, PaginateMixin):
    """
    View for getting active tokens of following users
    """

    @swagger_auto_schema(
        operation_description="post search pattern",
        responses={200: FollowingSerializer(many=True), 404: "User not found"},
    )
    def get(self, request, address):
        try:
            user = AdvUser.objects.get_by_custom_url(address)
        except ObjectDoesNotExist:
            return Response(
                {"error": "User not found"}, status=status.HTTP_404_NOT_FOUND
            )

        follow_queryset = UserAction.objects.filter(method="follow", whom_follow=user)
        followers_users = [action.user for action in follow_queryset]
        users = FollowingSerializer(followers_users, many=True).data
        return Response(self.paginate(request, users), status=status.HTTP_200_OK)


class VerificationView(APIView):
    """
    View for liking token.
    """

    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="like token",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "url": openapi.Schema(type=openapi.TYPE_STRING),
                "address": openapi.Schema(type=openapi.TYPE_STRING),
                "role": openapi.Schema(type=openapi.TYPE_STRING),
                "bio": openapi.Schema(type=openapi.TYPE_STRING),
                "twitter": openapi.Schema(type=openapi.TYPE_STRING),
                "media": openapi.Schema(type=openapi.TYPE_STRING),
                "instagram": openapi.Schema(type=openapi.TYPE_STRING),
                "website": openapi.Schema(type=openapi.TYPE_STRING),
                "email": openapi.Schema(type=openapi.TYPE_STRING),
            },
            required=["bio", "email"],
        ),
        responses={200: "Verification request sent", 400: "Request already sent"},
    )
    def post(self, request):
        user = request.user
        verification, created = VerificationForm.objects.get_or_create(user=user)
        if not created:
            return Response(
                {"error": "Request already sent"}, status=status.HTTP_400_BAD_REQUEST
            )
        verification.save_form(request)

        connection = get_email_connection()
        text = """
        New veridication request arrived!
        URL: https://{domain}/django-admin/accounts/advuser/{id}/change/
        """.format(
            domain=ALLOWED_HOSTS[0], id=user.id
        )

        send_mail(
            "New verification request",
            text,
            config.HOST_USER,
            [config.MAIL],
            connection=connection,
        )
        return Response("Verification request sent", status=status.HTTP_200_OK)


class SetUserCoverView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="set cover",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "cover": openapi.Schema(
                    type=openapi.TYPE_STRING, format=openapi.FORMAT_BINARY
                ),
            },
        ),
        responses={200: "OK", 400: "error"},
    )
    def post(self, request):
        user = request.user
        media = request.FILES.get("cover")
        if media:
            ipfs = send_to_ipfs(media)
            user.cover_ipfs = ipfs
            user.save()
        return Response(user.cover, status=status.HTTP_200_OK)


class GetRandomCoverView(APIView):
    @swagger_auto_schema(
        operation_description="get random cover",
        responses={200: CoverSerializer, 404: "error"},
    )
    def get(self, request):
        covers = (
            AdvUser.objects.exclude(cover_ipfs=None)
            .exclude(cover_ipfs="")
            .exclude(is_verificated=False)
        )
        if not covers:
            return Response(
                {"error": "there is no available cover"},
                status=status.HTTP_404_NOT_FOUND,
            )
        random_cover = random.choice(covers)
        response_data = CoverSerializer(random_cover).data
        return Response(response_data, status=status.HTTP_200_OK)
