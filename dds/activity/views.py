import datetime

from django.db.models import Q
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated

from dds.utilities import get_page_slice
from dds.consts import DECIMALS
from .models import BidsHistory, ListingHistory, TokenHistory, UserAction
from .utils import quick_sort
from .api import get_activity_response
from dds.accounts.serializers import UserSerializer
from dds.activity.serializers import UserStatSerializer
from dds.activity.services.top_users import get_top_users


class ActivityView(APIView):
    """
    View for get activities and filter by types
    """

    @swagger_auto_schema(
        operation_description="get activity",
        manual_parameters=[
            openapi.Parameter("type", openapi.IN_QUERY, type=openapi.TYPE_STRING),
            openapi.Parameter("page", openapi.IN_QUERY, type=openapi.TYPE_NUMBER),
        ],
    )
    def get(self, request):
        types = request.query_params.get("type")
        page = int(request.query_params.get("page"))

        start, end = get_page_slice(page)

        history_methods = {
            "purchase": "Buy",
            "sale": "Buy",
            "transfer": "Transfer",
            "mint": "Mint",
            "burn": "Burn",
        }
        action_methods = {
            "like": "like",
            "follow": "follow",
        }
        bids_methods = {
            "bids": "Bet",
        }

        activities = list()

        if types:
            for param, method in history_methods.items():
                if param in types:
                    items = TokenHistory.objects.filter(method=method).order_by(
                        "-date"
                    )[:end]
                    activities.extend(items)
            for param, method in action_methods.items():
                if param in types:
                    items = UserAction.objects.filter(method=method).order_by("-date")[
                        :end
                    ]
                    activities.extend(items)
            for param, method in bids_methods.items():
                if param in types:
                    items = BidsHistory.objects.filter(method=method).order_by("-date")[
                        :end
                    ]
                    activities.extend(items)
            if "list" in types:
                listing = ListingHistory.objects.all() \
                    .order_by("-date")[start:end]
                activities.extend(listing)
        else:
            actions = UserAction.objects.all().order_by("-date")[:end]
            activities.extend(actions)
            history = TokenHistory.objects.exclude(
                Q(method="Burn") | Q(method="Transfer")
            ).order_by("-date")[:end]
            activities.extend(history)
            bit = BidsHistory.objects.all().order_by("-date")[:end]
            activities.extend(bit)
            listing = ListingHistory.objects.all().order_by("-date")[:end]
            activities.extend(listing)

        quick_sort(activities)
        response_data = get_activity_response(activities)[start:end]
        return Response(response_data, status=status.HTTP_200_OK)

class NotificationActivityView(APIView):
    """
    View for get user notifications
    """
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="get user notifications, return last 5",
    )
    def get(self, request):
        address = request.user.username
        activities = list()
        end = 5

        new_owner_methods = [
            'Transfer',
            'Mint',
            'Burn',
        ]

        items = TokenHistory.objects.filter(
            new_owner__username=address,
            method__in=new_owner_methods,
            is_viewed=False,
        ).order_by("-date")[:end]
        activities.extend(items)

        buy = TokenHistory.objects.filter(
            old_owner__username=address,
            method='Buy',
            is_viewed=False,
        ).order_by("-date")[:end]
        activities.extend(buy)

        user_actions = UserAction.objects.filter(
            whom_follow__username=address,
            is_viewed=False,
        ).order_by("-date")[:end]
        activities.extend(user_actions)

        bids = BidsHistory.objects.filter(
            user__username=address,
            is_viewed=False,
        ).order_by("-date")[:end]
        activities.extend(bids)

        listing = ListingHistory.objects.filter(
            user__username=address,
            is_viewed=False,
        ).order_by("-date")[:end]
        activities.extend(listing)

        quick_sort(activities)
        response_data = get_activity_response(activities)[:end]
        return Response(response_data, status=status.HTTP_200_OK)

    @swagger_auto_schema(
        operation_description="Mark activity as viewed",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'activity_id': openapi.Schema(type=openapi.TYPE_NUMBER),
                'method': openapi.Schema(type=openapi.TYPE_STRING),
            }),
        responses={200: "Marked as viewed"},
    )
    def post(self, request):
        activity_id = request.data.get('activity_id')
        method = request.data.get('method')
        address = request.user.username
        new_owner_methods = [
            'Transfer',
            'Mint',
            'Burn',
        ]
        if method == "all":
            token_history = TokenHistory.objects.filter(
                new_owner__username=address,
                method__in=new_owner_methods,
                is_viewed=False,
            ).update(is_viewed=True)

            token_history = TokenHistory.objects.filter(
                old_owner__username=address,
                method="Buy",
                is_viewed=False,
            ).update(is_viewed=True)

            user_actions = UserAction.objects.filter(
                whom_follow__username=address,
                is_viewed=False,
            ).update(is_viewed=True)

            bids = BidsHistory.objects.filter(
                user__username=address,
                is_viewed=False,
            ).update(is_viewed=True)

            listing = ListingHistory.objects.filter(
                user__username=address,
                is_viewed=False,
            ).update(is_viewed=True)
            return Response('Marked all as viewed', status=status.HTTP_200_OK)

        methods = {
            "Transfer": TokenHistory,
            "Buy": TokenHistory,
            "Mint": TokenHistory,
            "Burn": TokenHistory,
            "like": UserAction,
            "follow": UserAction,
            "Bet": BidsHistory,
            "Listing": ListingHistory,
        }
        action = methods[method].objects.get(id=int(activity_id))
        action.is_viewed = True
        action.save()
        return Response('Marked as viewed', status=status.HTTP_200_OK)


class UserActivityView(APIView):
    """
    View for get users activities and filter by types
    """

    @swagger_auto_schema(
        operation_description="get user activity",
        manual_parameters=[
            openapi.Parameter("type", openapi.IN_QUERY, type=openapi.TYPE_STRING),
            openapi.Parameter("page", openapi.IN_QUERY, type=openapi.TYPE_NUMBER),
        ],
    )
    def get(self, request, address):
        types = request.query_params.get("type")
        page = int(request.query_params.get("page"))

        start, end = get_page_slice(page)

        token_transfer_methods = {
            "sale": "Buy",
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
            for param, method in token_transfer_methods.items():
                if param in types:
                    items = TokenHistory.objects.filter(
                        old_owner__username=address,
                        method=method,
                        is_viewed=False,
                    ).order_by("-date")[:end]
                    activities.extend(items)
            for param, method in token_methods.items():
                if param in types:
                    items = TokenHistory.objects.filter(
                        new_owner__username=address,
                        method=method,
                        is_viewed=False,
                    ).order_by("-date")[:end]
                    activities.extend(items)
            for param, method in action_methods.items():
                if param in types:
                    items = UserAction.objects.filter(
                        Q(user__username=address) | Q(whom_follow__username=address),
                        method=method,
                        is_viewed=False,
                    ).order_by("-date")[:end]
                    activities.extend(items)
            for param, method in bids_methods.items():
                if param in types:
                    items = BidsHistory.objects.filter(
                        user__username=address,
                        is_viewed=False,
                        method=method,
                    ).order_by("-date")[:end]
                    activities.extend(items)
            if "list" in types:
                listing = ListingHistory.objects.filter(
                    user__username=address,
                    is_viewed=False,
                ).order_by("-date")[:end]
                activities.extend(listing)
        else:
            new_owner_methods = [
                'Transfer',
                'Mint',
                'Burn',
            ]

            items = TokenHistory.objects.filter(
                new_owner__username=address,
                method__in=new_owner_methods,
                is_viewed=False,
            ).order_by("-date")[:end]
            activities.extend(items)

            buy = TokenHistory.objects.filter(
                old_owner__username=address,
                method='Buy',
                is_viewed=False,
            ).order_by("-date")[:end]
            activities.extend(buy)

            user_actions = UserAction.objects.filter(
                Q(user__username=address) | Q(whom_follow__username=address),
                is_viewed=False,
            ).order_by("-date")[:end]
            activities.extend(user_actions)

            listing = ListingHistory.objects.filter(user__username=address).order_by(
                "-date"
            )[:end]
            activities.extend(listing)

            bit = BidsHistory.objects.filter(user__username=address).order_by("-date")[:end]
            activities.extend(bit)

        quick_sort(activities)
        response_data = get_activity_response(activities)[start:end]
        return Response(response_data, status=status.HTTP_200_OK)


class FollowingActivityView(APIView):
    """
    View for get user following activities and filter by types
    """

    @swagger_auto_schema(
        operation_description="get user activity",
        manual_parameters=[
            openapi.Parameter("type", openapi.IN_QUERY, type=openapi.TYPE_STRING),
            openapi.Parameter("page", openapi.IN_QUERY, type=openapi.TYPE_NUMBER),
        ],
    )
    def get(self, request, address):
        types = request.query_params.get("type")
        page = int(request.query_params.get("page"))

        start, end = get_page_slice(page)

        token_transfer_methods = {
            "purchase": "Buy",
            "sale": "Buy",
            "transfer": "Transfer",
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
            method="follow",
            user__username=address,
        ).values_list("whom_follow_id", flat=True)

        if types:
            for param, method in token_transfer_methods.items():
                if param in types:
                    items = TokenHistory.objects.filter(
                        Q(new_owner__id__in=following_ids)
                        | Q(old_owner__id__in=following_ids),
                        method=method,
                    ).order_by("-date")[:end]
                    activities.extend(items)
            for param, method in action_methods.items():
                if param in types:
                    items = UserAction.objects.filter(
                        Q(user__id__in=following_ids)
                        | Q(whom_follow__id__in=following_ids),
                        method=method,
                    ).order_by("-date")[:end]
                    activities.extend(items)
            for param, method in token_methods.items():
                if param in types:
                    items = TokenHistory.objects.filter(
                        Q(new_owner__id__in=following_ids),
                        method=method,
                    ).order_by("-date")[:end]
                    activities.extend(items)
            for param, method in bids_methods.items():
                if param in types:
                    items = BidsHistory.objects.filter(
                        user__id__in=following_ids,
                        method=method,
                    ).order_by("-date")[:end]
                    activities.extend(items)
            if "list" in types:
                listing = ListingHistory.objects.filter(
                    user__id__in=following_ids,
                ).order_by("-date")[:end]
        else:
            actions = UserAction.objects.filter(
                Q(user__id__in=following_ids) | Q(whom_follow__id__in=following_ids)
            ).order_by("-date")[:end]
            activities.extend(actions)
            history = (
                TokenHistory.objects.filter(
                    Q(new_owner__id__in=following_ids)
                    | Q(old_owner__id__in=following_ids)
                )
                .exclude(Q(method="Burn") | Q(method="Transfer"))
                .order_by("-date")[:end]
            )
            activities.extend(history)
            listing = ListingHistory.objects.filter(
                user__id__in=following_ids
            ).order_by("-date")[:end]
            activities.extend(listing)
            bit = BidsHistory.objects.filter(user__id__in=following_ids).order_by("-date")[:end]
            activities.extend(bit)

        quick_sort(activities)
        response_data = get_activity_response(activities)[start:end]
        return Response(response_data, status=status.HTTP_200_OK)


class GetBestDealView(APIView):
    @swagger_auto_schema(
        operation_description="get top users",
        manual_parameters=[
            openapi.Parameter("type", openapi.IN_QUERY, type=openapi.TYPE_STRING),
            openapi.Parameter("sort_period", openapi.IN_QUERY, type=openapi.TYPE_STRING),
        ],
    )
    def get(self, request, days):
        type_ = request.query_params.get("type")                # seller, buyer
        sort_period = request.query_params.get("sort_period")   # day, week, month

        top_users = get_top_users(type_, sort_period)
        response_data = UserStatSerializer(top_users, many=True, context={
            "status": type_, 
            "time_range": sort_period,
        }).data 

        return Response(response_data, status=status.HTTP_200_OK)
