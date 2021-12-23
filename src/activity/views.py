from src.activity.serializers import UserStatSerializer, ActivitySerializer
from src.activity.services.top_users import get_top_users
from src.activity.services.top_collections import get_top_collections
from src.settings import config
from src.store.models import Token, Tags
from src.networks.models import Network
from src.utilities import PaginateMixin
from django.db.models import Q
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.permissions import (
    IsAuthenticated,
    IsAuthenticatedOrReadOnly,
)
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import BidsHistory, TokenHistory, UserAction
from .utils import quick_sort
from src.activity.services.price_history import PriceHistory


class ActivityView(APIView, PaginateMixin):
    """
    View for get activities and filter by types
    """

    @swagger_auto_schema(
        operation_description="get activity",
        manual_parameters=[
            openapi.Parameter("network", openapi.IN_QUERY, type=openapi.TYPE_STRING),
            openapi.Parameter("type", openapi.IN_QUERY, type=openapi.TYPE_STRING),
            openapi.Parameter("page", openapi.IN_QUERY, type=openapi.TYPE_STRING),
        ],
    )
    def get(self, request):
        network = request.query_params.get("network", config.DEFAULT_NETWORK)
        types = request.query_params.get("type")

        history_methods = {
            "purchase": "Buy",
            "sale": "Buy",
            "transfer": "Transfer",
            "mint": "Mint",
            "burn": "Burn",
            "list": "Listing",
        }
        action_methods = {
            "like": "like",
            "follow": "follow",
        }
        bids_methods = {
            "bids": "Bet",
        }

        activities = list()

        total_items = 0
        if types:
            for param, method in history_methods.items():
                if param in types:
                    items = TokenHistory.objects.filter(
                        method=method,
                        token__collection__network__name__icontains=network,
                    ).order_by("-date")
                    total_items += items.count()
                    activities.extend(items)
            for param, method in action_methods.items():
                if param in types:
                    items = UserAction.objects.filter(
                        Q(token__collection__network__name__icontains=network)
                        | Q(token__isnull=True),
                        method=method,
                    ).order_by("-date")
                    total_items += items.count()
                    activities.extend(items)
            for param, method in bids_methods.items():
                if param in types:
                    items = BidsHistory.objects.filter(
                        method=method,
                        token__collection__network__name__icontains=network,
                    ).order_by("-date")
                    total_items += items.count()
                    activities.extend(items)

        else:
            actions = UserAction.objects.filter(
                Q(token__collection__network__name__icontains=network)
                | Q(token__isnull=True),
            ).order_by("-date")
            history = (
                TokenHistory.objects.filter(
                    token__collection__network__name__icontains=network,
                )
                .exclude(method="Burn")
                .order_by("-date")
            )
            bids = BidsHistory.objects.filter(
                token__collection__network__name__icontains=network,
            ).order_by("-date")

            activities.extend(actions)
            activities.extend(history)
            activities.extend(bids)

        quick_sort(activities)
        items = ActivitySerializer(activities, many=True).data
        return Response(self.paginate(request, items), status=status.HTTP_200_OK)


class NotificationActivityView(APIView):
    """
    View for get user notifications
    """

    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="get user notifications, return last 5",
        manual_parameters=[
            openapi.Parameter("network", openapi.IN_QUERY, type=openapi.TYPE_STRING),
        ],
    )
    def get(self, request):
        address = request.user.username
        network = request.query_params.get("network", config.DEFAULT_NETWORK)
        activities = list()
        end = 5

        new_owner_methods = [
            "Transfer",
            "Mint",
            "Burn",
        ]
        old_owner_methods = ["Buy", "Listing"]

        items = TokenHistory.objects.filter(
            token__collection__network__name__icontains=network,
            new_owner__username=address,
            method__in=new_owner_methods,
            is_viewed=False,
        ).order_by("-date")[:end]
        activities.extend(items)

        buy_listing = TokenHistory.objects.filter(
            token__collection__network__name__icontains=network,
            old_owner__username=address,
            method__in=old_owner_methods,
            is_viewed=False,
        ).order_by("-date")[:end]
        activities.extend(buy_listing)

        user_actions = UserAction.objects.filter(
            Q(token__collection__network__name__icontains=network)
            | Q(token__isnull=True),
            whom_follow__username=address,
            is_viewed=False,
        ).order_by("-date")[:end]
        activities.extend(user_actions)

        bids = BidsHistory.objects.filter(
            token__collection__network__name__icontains=network,
            user__username=address,
            is_viewed=False,
        ).order_by("-date")[:end]
        activities.extend(bids)

        quick_sort(activities)
        response_data = ActivitySerializer(activities, many=True).data[:end]
        return Response(response_data, status=status.HTTP_200_OK)

    @swagger_auto_schema(
        operation_description="Mark activity as viewed. Method 'all' - marked all activity as viewed.",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "activity_id": openapi.Schema(type=openapi.TYPE_NUMBER),
                "method": openapi.Schema(type=openapi.TYPE_STRING),
            },
        ),
        responses={200: "Marked as viewed"},
    )
    def post(self, request):
        activity_id = request.data.get("activity_id")
        method = request.data.get("method")
        address = request.user.username
        new_owner_methods = [
            "Transfer",
            "Mint",
            "Burn",
        ]
        old_owner_methods = [
            "Buy",
            "Listing",
        ]
        if method == "all":
            TokenHistory.objects.filter(
                new_owner__username=address,
                method__in=new_owner_methods,
                is_viewed=False,
            ).update(is_viewed=True)

            TokenHistory.objects.filter(
                old_owner__username=address,
                method__in=old_owner_methods,
                is_viewed=False,
            ).update(is_viewed=True)

            UserAction.objects.filter(
                whom_follow__username=address,
                is_viewed=False,
            ).update(is_viewed=True)

            BidsHistory.objects.filter(
                user__username=address,
                is_viewed=False,
            ).update(is_viewed=True)

            return Response("Marked all as viewed", status=status.HTTP_200_OK)

        methods = {
            "Transfer": TokenHistory,
            "Buy": TokenHistory,
            "Mint": TokenHistory,
            "Burn": TokenHistory,
            "like": UserAction,
            "follow": UserAction,
            "Bet": BidsHistory,
            "Listing": TokenHistory,
        }
        action = methods[method].objects.get(id=int(activity_id))
        action.is_viewed = True
        action.save()
        return Response("Marked as viewed", status=status.HTTP_200_OK)


class UserActivityView(APIView, PaginateMixin):
    """
    View for get users activities and filter by types
    """

    @swagger_auto_schema(
        operation_description="get user activity",
        manual_parameters=[
            openapi.Parameter("network", openapi.IN_QUERY, type=openapi.TYPE_STRING),
            openapi.Parameter("type", openapi.IN_QUERY, type=openapi.TYPE_STRING),
            openapi.Parameter("page", openapi.IN_QUERY, type=openapi.TYPE_STRING),
        ],
    )
    def get(self, request, address):
        network = request.query_params.get("network", config.DEFAULT_NETWORK)
        types = request.query_params.get("type")

        old_owner_methods = {
            "sale": "Buy",
            "listing": "Listing",
        }
        action_methods = {
            "like": "like",
            "follow": "follow",
        }
        token_methods = {
            "purchase": "Buy",
            "mint": "Mint",
            "burn": "Burn",
            "transfer": "Transfer",
        }
        bids_methods = {
            "bids": "Bet",
        }

        activities = list()

        if types:
            for param, method in old_owner_methods.items():
                if param in types:
                    items = TokenHistory.objects.filter(
                        token__collection__network__name__icontains=network,
                        old_owner__username=address,
                        method=method,
                        is_viewed=False,
                    ).order_by("-date")
                    activities.extend(items)
            for param, method in token_methods.items():
                if param in types:
                    items = TokenHistory.objects.filter(
                        new_owner__username=address,
                        token__collection__network__name__icontains=network,
                        method=method,
                        is_viewed=False,
                    ).order_by("-date")
                    activities.extend(items)
            for param, method in action_methods.items():
                if param in types:
                    items = UserAction.objects.filter(
                        Q(user__username=address) | Q(whom_follow__username=address),
                        Q(token__collection__network__name__icontains=network)
                        | Q(token__isnull=True),
                        method=method,
                        is_viewed=False,
                    ).order_by("-date")
                    activities.extend(items)
            for param, method in bids_methods.items():
                if param in types:
                    items = BidsHistory.objects.filter(
                        token__collection__network__name__icontains=network,
                        user__username=address,
                        is_viewed=False,
                        method=method,
                    ).order_by("-date")
                    activities.extend(items)

        else:
            new_owner_methods = [
                "Transfer",
                "Mint",
                "Burn",
            ]

            old_owner_methods = [
                "Buy",
                "Listing",
            ]

            items = TokenHistory.objects.filter(
                token__collection__network__name__icontains=network,
                new_owner__username=address,
                method__in=new_owner_methods,
                is_viewed=False,
            ).order_by("-date")
            activities.extend(items)

            buy = TokenHistory.objects.filter(
                token__collection__network__name__icontains=network,
                old_owner__username=address,
                method__in=old_owner_methods,
                is_viewed=False,
            ).order_by("-date")
            activities.extend(buy)

            user_actions = UserAction.objects.filter(
                Q(token__collection__network__name__icontains=network)
                | Q(token__isnull=True),
                whom_follow__username=address,
                is_viewed=False,
            ).order_by("-date")
            activities.extend(user_actions)

            bids = BidsHistory.objects.filter(
                user__username=address,
                token__collection__network__name__icontains=network,
            ).order_by("-date")
            activities.extend(bids)

        quick_sort(activities)
        items = ActivitySerializer(activities, many=True).data
        return Response(self.paginate(request, items), status=status.HTTP_200_OK)


class FollowingActivityView(APIView, PaginateMixin):
    """
    View for get user following activities and filter by types
    """

    @swagger_auto_schema(
        operation_description="get user activity",
        manual_parameters=[
            openapi.Parameter("network", openapi.IN_QUERY, type=openapi.TYPE_STRING),
            openapi.Parameter("type", openapi.IN_QUERY, type=openapi.TYPE_STRING),
            openapi.Parameter("page", openapi.IN_QUERY, type=openapi.TYPE_STRING),
        ],
    )
    def get(self, request, address):
        network = request.query_params.get("network", config.DEFAULT_NETWORK)
        types = request.query_params.get("type")

        token_transfer_methods = {
            "purchase": "Buy",
            "sale": "Buy",
            "transfer": "Transfer",
            "list": "Listing",
        }
        action_methods = {
            "like": "like",
            "follow": "follow",
        }
        token_methods = {
            "mint": "Mint",
            "burn": "Burn",
        }
        bids_methods = {
            "bids": "Bet",
        }

        activities = list()

        following_ids = UserAction.objects.filter(
            Q(token__collection__network__name__icontains=network)
            | Q(token__isnull=True),
            method="follow",
            user__username=address,
        ).values_list("whom_follow_id", flat=True)

        if types:
            for param, method in token_transfer_methods.items():
                if param in types:
                    items = TokenHistory.objects.filter(
                        Q(new_owner__id__in=following_ids)
                        | Q(old_owner__id__in=following_ids),
                        token__collection__network__name__icontains=network,
                        method=method,
                    ).order_by("-date")
                    activities.extend(items)
            for param, method in action_methods.items():
                if param in types:
                    items = UserAction.objects.filter(
                        Q(token__collection__network__name__icontains=network)
                        | Q(token__isnull=True),
                        Q(user__id__in=following_ids)
                        | Q(whom_follow__id__in=following_ids),
                        method=method,
                    ).order_by("-date")
                    activities.extend(items)
            for param, method in token_methods.items():
                if param in types:
                    items = TokenHistory.objects.filter(
                        Q(new_owner__id__in=following_ids),
                        method=method,
                    ).order_by("-date")
                    activities.extend(items)
            for param, method in bids_methods.items():
                if param in types:
                    items = BidsHistory.objects.filter(
                        user__id__in=following_ids,
                        method=method,
                        token__collection__network__name__icontains=network,
                    ).order_by("-date")
                    activities.extend(items)

        else:
            actions = UserAction.objects.filter(
                Q(user__id__in=following_ids) | Q(whom_follow__id__in=following_ids),
                Q(token__collection__network__name__icontains=network)
                | Q(token__isnull=True),
            ).order_by("-date")
            activities.extend(actions)
            history = (
                TokenHistory.objects.filter(
                    Q(new_owner__id__in=following_ids)
                    | Q(old_owner__id__in=following_ids),
                    token__collection__network__name__icontains=network,
                )
                # .exclude(Q(method="Burn") | Q(method="Transfer"))
                .exclude(method="Burn").order_by("-date")
            )
            activities.extend(history)
            bids = BidsHistory.objects.filter(
                user__id__in=following_ids,
                token__collection__network__name__icontains=network,
            ).order_by("-date")
            activities.extend(bids)

        quick_sort(activities)
        items = ActivitySerializer(activities, many=True).data
        return Response(self.paginate(request, items), status=status.HTTP_200_OK)


class GetTopCollectionsView(APIView, PaginateMixin):
    @swagger_auto_schema(
        operation_description="get top collections",
        manual_parameters=[
            openapi.Parameter("network", openapi.IN_QUERY, type=openapi.TYPE_STRING),
            openapi.Parameter("tag", openapi.IN_QUERY, type=openapi.TYPE_STRING),
            openapi.Parameter(
                "sort_period",
                openapi.IN_QUERY,
                required=True,
                type=openapi.TYPE_STRING,
                description="day, week, month",
            ),
            openapi.Parameter(
                "order_by",
                openapi.IN_QUERY,
                type=openapi.TYPE_STRING,
                description="price, defference, floor_price, total_items, total_owners",
            ),
        ],
    )
    def get(self, request):
        sort_period = request.query_params.get(
            "sort_period", "month"
        )  # day, week, month
        order_by = request.query_params.get("order_by", "price")  # day, week, month
        network = request.query_params.get("network", config.DEFAULT_NETWORK)
        tag = request.query_params.get("tag")
        if tag is not None:
            tag = Tags.objects.filter(name=tag).first()
        collections = get_top_collections(network, sort_period, order_by, tag)
        return Response(self.paginate(request, collections), status=status.HTTP_200_OK)


class GetBestDealView(APIView):
    @swagger_auto_schema(
        operation_description="get top users",
        manual_parameters=[
            openapi.Parameter("network", openapi.IN_QUERY, type=openapi.TYPE_STRING),
            openapi.Parameter(
                "type",
                openapi.IN_QUERY,
                required=True,
                type=openapi.TYPE_STRING,
                description="seller, buyer, follows",
            ),
            openapi.Parameter(
                "sort_period",
                openapi.IN_QUERY,
                required=True,
                type=openapi.TYPE_STRING,
                description="day, week, month",
            ),
        ],
    )
    def get(self, request):
        type_ = request.query_params.get("type")  # seller, buyer, follows
        sort_period = request.query_params.get("sort_period")  # day, week, month
        network_name = request.query_params.get("network", config.DEFAULT_NETWORK)
        network = Network.objects.get(name__icontains=network_name)

        top_users = get_top_users(type_, sort_period, network)
        response_data = UserStatSerializer(
            top_users,
            many=True,
            context={
                "status": type_,
                "time_range": sort_period,
                "network": network,
            },
        ).data

        return Response(response_data, status=status.HTTP_200_OK)


class GetPriceHistory(APIView):
    """
    View for get price history of token id.
    """

    permission_classes = [IsAuthenticatedOrReadOnly]

    @swagger_auto_schema(
        operation_description="get price history",
        manual_parameters=[
            openapi.Parameter(
                "period",
                openapi.IN_QUERY,
                type=openapi.TYPE_STRING,
                description="day, week, month, year",
            ),
        ],
    )
    def get(self, request, id):
        period = request.query_params.get("period")

        try:
            token = Token.objects.committed().get(id=id)
        except Token.DoesNotExist:
            return Response("token not found", status=status.HTTP_404_NOT_FOUND)

        if period not in ["day", "week", "month", "year"]:
            return Response("unknown period", status=status.HTTP_400_BAD_REQUEST)

        response = PriceHistory(token, period).get_history()
        return Response(response, status=status.HTTP_200_OK)
