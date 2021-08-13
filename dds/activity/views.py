import datetime

from django.db.models import Q
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from dds.consts import DECIMALS
from .models import BidsHistory, ListingHistory, TokenHistory, UserAction
from .utils import quick_sort
from .api import get_activity_response


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

        start = (page - 1) * 50
        end = page * 50

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


class UserActivityView(APIView):
    """
    View for get users activities and filter by types
    """

    @swagger_auto_schema(
        operation_description="get user activity",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={"address": openapi.Schema(type=openapi.TYPE_STRING)},
        ),
        manual_parameters=[
            openapi.Parameter("type", openapi.IN_QUERY, type=openapi.TYPE_STRING),
            openapi.Parameter("page", openapi.IN_QUERY, type=openapi.TYPE_NUMBER),
        ],
    )
    def get(self, request, address):
        types = request.query_params.get("type")
        page = int(request.query_params.get("page"))

        start = (page - 1) * 50
        end = page * 50

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

        if types:
            for param, method in token_transfer_methods.items():
                if param in types:
                    items = TokenHistory.objects.filter(
                        Q(new_owner__username=address) | Q(old_owner__username=address),
                        method=method,
                    ).order_by("-date")[:end]
                    activities.extend(items)
            for param, method in action_methods.items():
                if param in types:
                    items = UserAction.objects.filter(
                        Q(user__username=address) | Q(whom_follow__username=address),
                        method=method,
                    ).order_by("-date")[:end]
                    activities.extend(items)
            for param, method in token_methods.items():
                if param in types:
                    items = TokenHistory.objects.filter(
                        Q(new_owner__username=address),
                        method=method,
                    ).order_by("-date")[:end]
                    activities.extend(items)
            for param, method in bids_methods.items():
                if param in types:
                    items = BidsHistory.objects.filter(
                        user__username=address,
                        method=method,
                    ).order_by("-date")[:end]
                    activities.extend(items)
        else:
            actions = UserAction.objects.filter(
                Q(user__username=address) | Q(whom_follow__username=address)
            ).order_by("-date")[:end]
            activities.extend(actions)
            history = (
                TokenHistory.objects.filter(
                    Q(new_owner__username=address) | Q(old_owner__username=address)
                )
                .exclude(Q(method="Burn") | Q(method="Transfer"))
                .order_by("-date")[:end]
            )
            activities.extend(history)
            listing = ListingHistory.objects.filter(user__username=address).order_by(
                "-date"
            )[:end]
            activities.extend(listing)

        quick_sort(activities)
        response_data = get_activity_response(activities)[start:end]
        return Response(response_data, status=status.HTTP_200_OK)


class FollowingActivityView(APIView):
    """
    View for get user following activities and filter by types
    """

    @swagger_auto_schema(
        operation_description="get user activity",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={"address": openapi.Schema(type=openapi.TYPE_STRING)},
        ),
        manual_parameters=[
            openapi.Parameter("type", openapi.IN_QUERY, type=openapi.TYPE_STRING),
            openapi.Parameter("page", openapi.IN_QUERY, type=openapi.TYPE_NUMBER),
        ],
    )
    def get(self, request, address):
        types = request.query_params.get("type")
        page = int(request.query_params.get("page"))

        start = (page - 1) * 50
        end = page * 50

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

        quick_sort(activities)
        response_data = get_activity_response(activities)[start:end]
        return Response(response_data, status=status.HTTP_200_OK)


class GetBestDealView(APIView):

    def get(self, request, days):

        end_date = datetime.datetime.today()
        start_date = end_date - datetime.timedelta(days=days)

        tokens = TokenHistory.objects.filter(method='Buy').filter(date__range=[start_date, end_date])

        buyers = {}
        sellers = {}
        for token in tokens:
            buyer = token.new_owner.username
            seller = token.old_owner.username
            cost = token.price
            if len(buyers) < 15:
                if buyers.get(buyer):
                    buyers[buyer] += cost
                else:
                    buyers[buyer] = cost
            if len(sellers) < 15:
                if sellers.get(seller):
                    sellers[seller] += cost
                else:
                    sellers[seller] = cost

        buyers_list = []
        sellers_list = []
        buyers_list.append(buyers)
        sellers_list.append(sellers)

        return Response({'buyers': buyers_list, 'sellers': sellers_list}, status=status.HTTP_200_OK)
