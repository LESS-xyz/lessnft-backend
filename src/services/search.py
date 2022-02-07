import json
import logging
import operator
from abc import ABC, abstractmethod
from datetime import datetime
from decimal import Decimal

from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Count, Exists, OuterRef, Q
from django.utils import timezone

from src.accounts.models import AdvUser
from src.accounts.serializers import UserSearchSerializer
from src.rates.api import calculate_amount
from src.store.models import Bid, Collection, Ownership, Token
from src.store.serializers import CollectionSearchSerializer, TokenSerializer


class SearchABC(ABC):
    @abstractmethod
    def initial(self):
        """initial items and serializer"""
        ...

    def remove_unused_kwargs(self, kwargs):
        kwargs.pop("page", None)

    def parse(self, **kwargs):
        self.initial()
        self.remove_unused_kwargs(kwargs)

        current_user = kwargs.pop("current_user", None)
        order_by = kwargs.pop("order_by", None)

        for method, value in kwargs.items():
            try:
                getattr(self, method)(value)
            except AttributeError as e:
                logging.warning(e)
            except Exception as e:
                logging.error(e)

        if order_by and hasattr(self, "order_by"):
            self.order_by(order_by)

        return self.serializer(
            self.items,
            context={"user": current_user},
            many=True,
        ).data


class SearchToken(SearchABC):
    def initial(self):
        self.items = Token.objects.committed()
        self.serializer = TokenSerializer

    def network(self, network):
        if network and network[0]:
            if not network[0].lower() == "undefined":
                networks = network[0].split(",")
                self.items = self.items.filter(collection__network__name__in=networks)

    def tags(self, tags):
        if tags and tags[0]:
            tags = tags[0].split(",")
            self.items = self.items.filter(tags__name__in=tags).distinct()

    def text(self, words):
        if words and words[0]:
            words = words[0].split(" ")
            for word in words:
                self.items = self.items.filter(name__icontains=word)

    def stats(self, stats):
        if stats and stats[0]:
            stats = json.loads(stats[0])
            for stat, value in stats.items():
                min_data = value.get("min")
                max_data = value.get("max")
                stat_filters = {}
                if min_data:
                    stat_filters[f"_stats__{stat}__value__gte"] = float(min_data)
                if max_data:
                    stat_filters[f"_stats__{stat}__value__lte"] = float(max_data)
                self.items = self.items.filter(**stat_filters)

    def rankings(self, rankings):
        if rankings and rankings[0]:
            rankings = json.loads(rankings[0])
            for rank, value in rankings.items():
                min_data = value.get("min")
                max_data = value.get("max")
                rank_filters = {}
                if min_data:
                    rank_filters[f"_rankings__{rank}__value__gte"] = float(min_data)
                if max_data:
                    rank_filters[f"_rankings__{rank}__value__lte"] = float(max_data)
                self.items = self.items.filter(**rank_filters)

    def properties(self, properties):
        if properties and properties[0]:
            props = json.loads(properties[0])
            for prop, value in props.items():
                if value:
                    props_filter = {f"_properties__{prop}__value__in": value}
                    self.items = self.items.filter(**props_filter)

    def is_verified(self, is_verified):
        if is_verified is not None:
            is_verified = is_verified[0]
            is_verified = is_verified.lower() == "true"
            self.items = self.items.filter(
                Q(owner__is_verificated=is_verified)
                | Q(owners__is_verificated=is_verified)
            )

    def _price_filter_tokens(self, price, type_):
        relate = operator.gt
        if type_ == "max_price":
            relate = operator.lt

        if price and price[0] and str(price[0]).isdigit():
            min_price = Decimal(price[0])

            tokens = self.items
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
            self.items = Token.objects.filter(id__in=token_ids)

    def min_price(self, price):
        self._price_filter_tokens(price, "min_price")

    def max_price(self, price):
        self._price_filter_tokens(price, "max_price")

    def collections(self, collections):
        if collections and collections[0]:
            collections = collections[0].split(",")
            collection_ids = [col for col in collections if str(col).isdigit()]
            collection_short = [col for col in collections if col not in collection_ids]
            self.items = self.items.filter(
                Q(collection__id__in=collection_ids)
                | Q(collection__short_url__in=collection_short)
            )

    def owner(self, owner):
        if owner:
            try:
                owner = AdvUser.objects.get_by_custom_url(owner[0])
            except ObjectDoesNotExist:
                owner = None
            self.items = self.items.filter(
                Q(owner=owner) | Q(owners=owner),
            ).order_by("-id")

    def creator(self, creator):
        if creator:
            try:
                creator = AdvUser.objects.get_by_custom_url(creator[0])
                self.items = self.items.filter(creator=creator).order_by("-id")
            except ObjectDoesNotExist:
                self.items = Token.objects.none()

    def currency(self, currency):
        if currency and currency[0]:
            currencies = currency[0].split(",")
            self.items = self.items.filter(currency__symbol__in=currencies)

    def on_sale(self, on_sale):
        if on_sale and on_sale[0]:
            filter = "filter" if on_sale[0].lower() == "true" else "exclude"
            self.items = getattr(self.items, filter)(
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
        if on_sale and on_sale[0]:
            filter = "filter" if on_sale[0].lower() == "true" else "exclude"
            self.items = getattr(self.items, filter)(
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
            self.items = getattr(self.items, filter)(
                selling=True,
                currency_price__isnull=True,
                start_auction__lte=timezone.now(),
                end_auction__gte=timezone.now(),
            )

    def has_bids(self, has_bids):
        if has_bids:
            filter = "filter" if has_bids[0].lower() == "true" else "exclude"
            self.items = getattr(self.items, filter)(
                Exists(Bid.objects.filter(token__id=OuterRef("id")))
            )

    def bids_by(self, user_):
        if user_ is not None:
            try:
                user = AdvUser.objects.get_by_custom_url(user_[0])
            except AdvUser.DoesNotExist:
                user = None
            if user:
                self.items = self.items.filter(
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
        if history and history.date:
            return history.date
        return timezone.make_aware(datetime.fromtimestamp(0))

    def order_by_transfer(self, token):
        history = (
            token.tokenhistory_set.filter(method="Transfer").order_by("date").last()
        )
        if history and history.date:
            return history.date
        return timezone.make_aware(datetime.fromtimestamp(0))

    def order_by_auction_end(self, token):
        default_value = timezone.make_aware(datetime.fromtimestamp(0))
        if token.is_timed_auc_selling:
            return token.end_auction
        return default_value

    def order_by_last_sale(self, token):
        history = token.tokenhistory_set.filter(method="Buy").order_by("date").last()
        if history and history.price:
            return history.price
        return 0

    def order_by(self, order_by):
        tokens = list(self.items)
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

        self.items = tokens


class SearchCollection(SearchABC):
    def initial(self):
        self.items = Collection.objects.committed()
        self.serializer = CollectionSearchSerializer

    def tags(self, tags):
        if tags and tags[0]:
            tags = tags[0].split(",")
            self.items = self.items.filter(
                Exists(
                    Token.objects.committed().filter(
                        tags__name__in=tags,
                        collection__id=OuterRef("id"),
                    )
                )
            )

    def creator(self, user):
        if user and user[0]:
            try:
                user = AdvUser.objects.get_by_custom_url(user[0])
                self.items = self.items.filter(creator=user)
            except ObjectDoesNotExist:
                self.items = Collection.objects.none()

    def text(self, words):
        if words and words[0]:
            words = words[0].split(" ")
            for word in words:
                self.items = self.items.filter(name__icontains=word)

    def network(self, network):
        if network and network[0]:
            if not network[0].lower() == "undefined":
                networks = network[0].split(",")
                self.items = self.items.filter(network__name__in=networks)


class SearchUser(SearchABC):
    def initial(self):
        self.items = AdvUser.objects.all()
        self.serializer = UserSearchSerializer

    def text(self, words):
        if words and words[0]:
            words = words[0].split(" ")
            for word in words:
                self.items = self.items.filter(display_name__icontains=word)

    def verificated(self, verificated):
        self.items = self.items.filter(is_verificated=verificated[0].lower() == "true")

    def order_by_created(self, reverse):
        return self.items.order_by(f"{reverse}id")

    def order_by_followers(self, reverse):
        return self.items.annotate(follow_count=Count("following")).order_by(
            f"{reverse}follow_count"
        )

    def order_by_tokens_created(self, reverse):
        return self.items.annotate(creators=Count("token_creator")).order_by(
            f"{reverse}creators"
        )

    def order_by(self, order_by):
        reverse = "-" if order_by[0] == "-" else ""
        order_by = order_by.strip("-")
        try:
            users = getattr(self, f"order_by_{order_by}")(reverse)
        except AttributeError:
            logging.warning(f"Unknown token sort method {order_by}")
        self.items = users


Search = {
    "token": SearchToken(),
    "collection": SearchCollection(),
    "user": SearchUser(),
}
