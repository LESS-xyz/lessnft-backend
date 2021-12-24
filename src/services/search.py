import logging
import operator
from decimal import Decimal

from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Count, Exists, OuterRef, Q
from django.utils import timezone

from src.accounts.models import AdvUser
from src.accounts.serializers import UserSearchSerializer
from src.rates.api import calculate_amount
from src.store.models import Bid, Collection, Ownership, Token
from src.store.serializers import CollectionSearchSerializer, TokenSerializer
from src.utilities import get_page_slice


class SearchToken:
    def __init__(self):
        self.tokens = None

    def network(self, network):
        if network and network[0]:
            if not network[0].lower() == "undefined":
                networks = network[0].split(",")
                self.tokens = self.tokens.filter(collection__network__name__in=networks)

    def tags(self, tags):
        if tags and tags[0]:
            tags = tags[0].split(",")
            self.tokens = self.tokens.filter(tags__name__in=tags).distinct()

    def text(self, words):
        if words and words[0]:
            words = words[0].split(" ")
            for word in words:
                self.tokens = self.tokens.filter(name__icontains=word)

    def is_verified(self, is_verified):
        if is_verified is not None:
            is_verified = is_verified[0]
            is_verified = is_verified.lower() == "true"
            self.tokens = self.tokens.filter(
                Q(owner__is_verificated=is_verified)
                | Q(owners__is_verificated=is_verified)
            )

    def _price_filter_tokens(self, price, type_):
        relate = operator.gt
        if type_ == "max_price":
            relate = operator.lt

        if price and price[0]:
            min_price = Decimal(price[0])

            tokens = self.tokens
            ownerships = Ownership.objects.filter(token__in=tokens)
            ownerships = [
                ownership.token.id
                for ownership in ownerships
                if ownership.usd_price and relate(ownership.usd_price, min_price)
            ]
            tokens = [
                token
                for token in tokens
                if token.usd_price and relate(token.usd_price, min_price)
            ]

            token_ids = [token.id for token in tokens]
            token_ids.extend(ownerships)
            self.tokens = Token.objects.filter(id__in=token_ids)

    def min_price(self, price):
        self._price_filter_tokens(price, "min_price")

    def max_price(self, price):
        self._price_filter_tokens(price, "max_price")

    def collections(self, collections):
        if collections and collections[0]:
            collections = collections[0].split(",")
            self.tokens = self.tokens.filter(collections__name__in=collections)

    def owner(self, owner):
        if owner:
            try:
                owner = AdvUser.objects.get_by_custom_url(owner[0])
            except ObjectDoesNotExist:
                owner = None
            self.tokens = self.tokens.filter(
                Q(owner=owner) | Q(owners=owner),
            ).order_by("-id")

    def creator(self, creator):
        if creator:
            try:
                creator = AdvUser.objects.get_by_custom_url(creator[0])
            except ObjectDoesNotExist:
                creator = None
            self.tokens = self.tokens.filter(creator=creator).order_by("-id")

    def currency(self, currency):
        if currency and currency[0]:
            currencies = currency[0].split(",")
            self.tokens = self.tokens.filter(currency__symbol__in=currencies)

    def on_sale(self, on_sale):
        if on_sale and on_sale[0] != "":
            filter = "filter" if on_sale[0].lower() == "true" else "exclude"
            self.tokens = getattr(self.tokens, filter)(
                Q(selling=True, currency_price__isnull=False, currency__isnull=False)
                | Q(
                    Exists(
                        Ownership.objects.filter(
                            token__id=OuterRef("id"),
                            selling=True,
                            currency_price__isnull=False,
                        )
                    )
                )
            )

    def on_auc_sale(self, on_sale):
        if on_sale and on_sale[0] != "":
            filter = "filter" if on_sale[0].lower() == "true" else "exclude"
            self.tokens = getattr(self.tokens, filter)(
                Q(
                    selling=True,
                    currency_minimal_bid__isnull=False,
                    currency__isnull=False,
                )
                | Q(
                    Exists(
                        Ownership.objects.filter(
                            token__id=OuterRef("id"),
                            selling=True,
                            currency_price__isnull=True,
                            currency_minimal_bid__isnull=False,
                        )
                    )
                )
            )

    def on_timed_auc_sale(self, on_sale):
        if on_sale and on_sale[0] != "":
            filter = "filter" if on_sale[0].lower() == "true" else "exclude"
            self.tokens = getattr(self.tokens, filter)(
                selling=True,
                currency_price__isnull=True,
                start_auction__lte=timezone.now(),
                end_auction__gte=timezone.now(),
            )

    def has_bids(self, has_bids):
        if has_bids:
            filter = "filter" if has_bids[0].lower() == "true" else "exclude"
            self.tokens = getattr(self.tokens, filter)(
                Exists(Bid.objects.filter(token__id=OuterRef("id")))
            )

    def bids_by(self, user_):
        if user_ is not None:
            try:
                user = AdvUser.objects.get_by_custom_url(user_[0])
            except AdvUser.DoesNotExist:
                user = None
            if user:
                self.tokens = self.tokens.filter(
                    Exists(
                        Bid.objects.filter(
                            token__id=OuterRef("id"),
                            user=user,
                        )
                    )
                )

    def order_by_price(self, token, reverse=False):
        currency = token.currency.symbol
        if not token.selling:
            return 0
        if token.standart == "ERC721":
            price = token.price if token.currency_price else token.minimal_bid
            return calculate_amount(price, currency)[0]
        owners = token.ownership_set.all()
        prices = [
            owner.get_currency_price for owner in owners if owner.get_currency_price
        ]
        prices = [calculate_amount(price, currency)[0] for price in prices]
        if reverse:
            return max(prices)
        return min(prices)

    def order_by_likes(self, token):
        return token.useraction_set.filter(method="like").count()

    def order_by_created_at(self, token):
        return token.updated_at

    def order_by_views(self, token):
        return token.viewstracker_set.count()

    def order_by_sale(self, token):
        history = token.tokenhistory_set.filter(method="Buy").order_by("date").last()
        if history:
            return history.date

    def order_by_transfer(self, token):
        history = (
            token.tokenhistory_set.filter(method="Transfer").order_by("date").last()
        )
        if history:
            return history.date

    def order_by_auction_end(self, token):
        if token.is_timed_auc_selling:
            return token.end_auction

    def order_by_last_sale(self, token):
        history = token.tokenhistory_set.filter(method="Buy").order_by("date").last()
        if history:
            return history.price

    def order_by(self, order_by):
        tokens = list(self.tokens)
        reverse = False
        if order_by is not None:
            order_by = order_by[0]
            if order_by.startswith("-"):
                order_by = order_by[1:]
                reverse = True

        try:
            tokens = sorted(
                tokens, key=getattr(self, f"order_by_{order_by}"), reverse=reverse
            )
        except AttributeError:
            logging.warning(f"Unknown token sort method {order_by}")

        self.tokens = tokens

    def parse(self, **kwargs):
        self.tokens = Token.objects.committed()
        kwargs.pop("page", None)
        current_user = kwargs.pop("current_user", None)
        order_by = kwargs.pop("order_by", None)

        for method, value in kwargs.items():
            try:
                getattr(self, method)(value)
            except AttributeError as e:
                logging.warning(e)
            except Exception as e:
                logging.error(e)

        if order_by:
            self.order_by(order_by)

        return TokenSerializer(
            self.tokens,
            context={"user": current_user},
            many=True,
        ).data


class SearchCollection:
    def tags(self, tags):
        if tags and tags[0]:
            tags = tags[0].split(",")
            self.collections = self.collections.filter(tags__name__in=tags).distinct()

    def creator(self, user):
        if user and user[0]:
            user = AdvUser.objects.get_by_custom_url(user[0])
            self.collections = self.collections.filter(creator=user)

    def text(self, words):
        words = words.split(" ")
        for word in words:
            self.collections = self.collections.filter(name__icontains=word)

    def network(self, network):
        return
        if network and network[0]:
            if not network[0].lower() == "undefined":
                networks = network[0].split(",")
                self.collections = self.collections.filter(network__name__in=networks)

    def parse(self, **kwargs):
        self.collections = Collection.objects.committed()
        page = kwargs.pop("page", [1])
        kwargs.pop("current_user", None)
        kwargs.pop("order_by", None)

        for method, value in kwargs.items():
            try:
                getattr(self, method)(value)
            except AttributeError:
                logging.warning(f"Unknown collection filter {method}")

        page = int(page[0])
        collections_count = len(self.collections)
        start, end = get_page_slice(page, collections_count, items_per_page=8)
        return CollectionSearchSerializer(self.collections[start:end], many=True).data


class SearchUser:
    def text(self, words):
        words = words.split(" ")
        for word in words:
            self.users = self.users.filter(display_name__icontains=word)

    def verificated(self, verificated):
        self.users = self.users.filter(is_verificated=verificated[0].lower() == "true")

    def order_by_created(self, reverse):
        return self.users.order_by(f"{reverse}id")

    def order_by_followers(self, reverse):
        return self.users.annotate(follow_count=Count("following")).order_by(
            f"{reverse}follow_count"
        )

    def order_by_tokens_created(self, reverse):
        return self.users.annotate(Count("token_creator")).order_by(
            f"{reverse}token_creator"
        )

    def order_by(self, order_by):
        reverse = "-" if order_by[0] == "-" else ""
        try:
            users = getattr(self, f"order_by_{order_by}")(reverse)
        except AttributeError:
            logging.warning(f"Unknown token sort method {order_by}")
        self.users = users

    def parse(self, **kwargs):
        self.users = AdvUser.objects.all()
        page = kwargs.pop("page", [1])
        order_by = kwargs.pop("order_by", None)
        kwargs.pop("current_user", None)

        for method, value in kwargs.items():
            try:
                getattr(self, method)(value)
            except AttributeError:
                logging.warning(f"Unknown collection filter {method}")

        if order_by:
            self.order_by(order_by)

        page = int(page[0])
        users_count = len(self.users)
        start, end = get_page_slice(page, users_count, items_per_page=8)
        return UserSearchSerializer(self.users[start:end], many=True).data


Search = {
    "token": SearchToken(),
    "collection": SearchCollection(),
    "user": SearchUser(),
}
