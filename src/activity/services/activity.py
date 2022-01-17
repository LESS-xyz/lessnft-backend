from typing import List

from django.db.models import Q

from src.activity.models import BidsHistory, TokenHistory, UserAction
from src.activity.utils import quick_sort


class ActivityBase:
    def get_methods(self, type_) -> List[str]:
        method = getattr(self, f"{type_}_methods")
        if self.types:
            methods_list = {
                method[type_] for type_ in self.types if type_ in method.keys()
            }
        else:
            methods_list = set(method.values())
        return list(methods_list)


class Activity(ActivityBase):
    def __init__(self, network, types):
        self.network = network
        self.types = types
        self.history_methods = {
            "purchase": "Buy",
            "sale": "Buy",
            "transfer": "Transfer",
            "mint": "Mint",
            "burn": "Burn",
            "list": "Listing",
        }
        self.action_methods = {
            "like": "like",
            "follow": "follow",
        }
        self.bids_methods = {
            "bids": "Bet",
        }

    def get_token_history(self):
        methods = self.get_methods("history")
        return TokenHistory.objects.filter(
            method__in=methods,
            token__collection__network__name__icontains=self.network,
            token__deleted=False,
        ).order_by("-date")

    def get_user_action(self):
        methods = self.get_methods("action")
        return UserAction.objects.filter(
            Q(token__collection__network__name__icontains=self.network)
            | Q(token__isnull=True),
            method__in=methods,
            token__deleted=False,
        ).order_by("-date")

    def get_bids_history(self):
        methods = self.get_methods("bids")
        return BidsHistory.objects.filter(
            method__in=methods,
            token__collection__network__name__icontains=self.network,
            token__deleted=False,
        ).order_by("-date")

    def get_activity(self):
        activities = list()
        activities.extend(self.get_token_history())
        activities.extend(self.get_user_action())
        activities.extend(self.get_bids_history())
        quick_sort(activities)
        return activities


class UserActivity(ActivityBase):
    def __init__(self, network, types, user):
        self.network = network
        self.types = types
        self.user = user
        self.old_owner_methods = {
            "sale": "Buy",
            "listing": "Listing",
        }
        self.new_owner_methods = {
            "purchase": "Buy",
            "mint": "Mint",
            "burn": "Burn",
            "transfer": "Transfer",
        }
        self.action_methods = {
            "like": "like",
            "follow": "follow",
        }
        self.bids_methods = {
            "bids": "Bet",
        }

    def get_new_owner_history(self):
        methods = self.get_methods("new_owner")
        return TokenHistory.objects.filter(
            new_owner__username=self.user,
            token__collection__network__name__icontains=self.network,
            method__in=methods,
            token__deleted=False,
        ).order_by("-date")

    def get_old_owner_history(self):
        methods = self.get_methods("old_owner")
        return TokenHistory.objects.filter(
            token__collection__network__name__icontains=self.network,
            old_owner__username=self.user,
            method__in=methods,
            token__deleted=False,
        ).order_by("-date")

    def get_user_action(self):
        methods = self.get_methods("action")
        return UserAction.objects.filter(
            Q(user__username=self.user) | Q(whom_follow__username=self.user),
            Q(token__collection__network__name__icontains=self.network)
            | Q(token__isnull=True),
            method__in=methods,
            token__deleted=False,
        ).order_by("-date")

    def get_bids_history(self):
        methods = self.get_methods("bids")
        return BidsHistory.objects.filter(
            token__collection__network__name__icontains=self.network,
            user__username=self.user,
            method__in=methods,
            token__deleted=False,
        ).order_by("-date")

    def get_activity(self):
        activities = list()
        activities.extend(self.get_new_owner_history())
        activities.extend(self.get_old_owner_history())
        activities.extend(self.get_user_action())
        activities.extend(self.get_bids_history())
        quick_sort(activities)
        return activities


class FollowingActivity(ActivityBase):
    def __init__(self, network, types, following_ids):
        self.network = network
        self.types = types
        self.following_ids = following_ids
        self.token_methods = {
            "mint": "Mint",
            "burn": "Burn",
        }
        self.transfer_methods = {
            "purchase": "Buy",
            "sale": "Buy",
            "transfer": "Transfer",
            "list": "Listing",
        }
        self.action_methods = {
            "like": "like",
            "follow": "follow",
        }
        self.bids_methods = {
            "bids": "Bet",
        }

    def get_transfer_history(self):
        methods = self.get_methods("transfer")
        return TokenHistory.objects.filter(
            Q(new_owner__id__in=self.following_ids)
            | Q(old_owner__id__in=self.following_ids),
            token__collection__network__name__icontains=self.network,
            method__in=methods,
            token__deleted=False,
        ).order_by("-date")

    def get_token_history(self):
        methods = self.get_methods("token")
        return TokenHistory.objects.filter(
            Q(new_owner__id__in=self.following_ids),
            method__in=methods,
            token__deleted=False,
        ).order_by("-date")

    def get_user_action(self):
        methods = self.get_methods("action")
        return UserAction.objects.filter(
            Q(token__collection__network__name__icontains=self.network)
            | Q(token__isnull=True),
            Q(user__id__in=self.following_ids)
            | Q(whom_follow__id__in=self.following_ids),
            method__in=methods,
            token__deleted=False,
        ).order_by("-date")

    def get_bids_history(self):
        methods = self.get_methods("bids")
        return BidsHistory.objects.filter(
            user__id__in=self.following_ids,
            method__in=methods,
            token__collection__network__name__icontains=self.network,
            token__deleted=False,
        ).order_by("-date")

    def get_activity(self):
        activities = list()
        activities.extend(self.get_transfer_history())
        activities.extend(self.get_token_history())
        activities.extend(self.get_user_action())
        activities.extend(self.get_bids_history())
        quick_sort(activities)
        return activities
