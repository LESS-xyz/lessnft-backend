from decimal import Decimal
from django.db.models import Q, Count

from dds.utilities import get_page_slice
from dds.store.models import Token, Collection, Ownership
from dds.store.serializers import TokenSerializer, CollectionSearchSerializer
from dds.rates.api import calculate_amount

from dds.accounts.models import AdvUser
from dds.accounts.serializers import UserSearchSerializer


class Search:
    def user_search(self, **kwargs):
        words = kwargs.get('words').split(' ')
        verificated = kwargs.get('verificated')
        page = kwargs.get('page', [1])
        order_by = kwargs.get('order_by')
        if order_by:
            reverse = "-" if order_by[0] == "-" else ""

        users = AdvUser.objects.all()
        users_count = users.count()

        if verificated is not None:
            users = users.filter(is_verificated=verificated[0].lower()=="true")

        for word in words:
            users = users.filter(display_name__icontains=word)

        if order_by == "created":
            users = users.order_by(f"{reverse}id")
        elif order_by == "followers":
            users = users.annotate(follow_count = Count('following')).order_by(f"{reverse}follow_count")
        elif order_by == "tokens_created":
            users = users.annotate(Count('token_creator')).order_by(f"{reverse}token_creator")

        start, end = get_page_slice(int(page[0]), len(users))
        return users_count, UserSearchSerializer(users[start:end], many=True).data

    def token_selling_filter(self, is_selling) -> bool:
        def token_filter(token):
            if is_selling:
                return token.is_selling or token.is_auc_selling
            return not token.is_selling and not token.is_auc_selling
        return token_filter

    def token_sort_price(self, token, reverse=False):
        currency = token.currency.symbol
        if not (token.is_selling or token.is_auc_selling):
            return 0
        if token.standart=="ERC721":
            price = token.price if token.currency_price else token.minimal_bid
            return calculate_amount(price, currency)[0]
        owners = token.ownership_set.all()
        prices = [calculate_amount(owner.get_currency_price, currency)[0] for owner in owners]
        if reverse:
            return max(prices)
        return min(prices)

    def token_sort_likes(self, token, reverse=False):
        return token.useraction_set.filter(method="like").count()

    def token_sort_updated_at(self, token, reverse=False):
        return token.updated_at

    def token_search(self, **kwargs):
        words = kwargs.get("words").split(' ')
        tags = kwargs.get("tags")
        is_verified = kwargs.get("is_verified")
        max_price = kwargs.get("max_price")
        order_by = kwargs.get("order_by")
        on_sale = kwargs.get("on_sale")
        currency = kwargs.get("currency")
        page = kwargs.get("page", [1])
        network = kwargs.get("network")
        user = kwargs.get("user")
        creator = kwargs.get("creator")
        owner = kwargs.get("owner")
        if currency is not None:
            currency = currency[0]
        tokens = Token.token_objects.network(network[0]).select_related("currency", "owner")
        # Below are the tokens in the form of a QUERYSET
        if owner:
            tokens = tokens.filter(
                Q(owner=owner) | Q(owners=owner),
            ).order_by('-id')

        if creator:
            tokens = tokens.filter(creator=creator).order_by('-id')

        for word in words:
            tokens = tokens.filter(name__icontains=word)

        if tags is not None:
            tags = tags[0].split(",")
            tokens = tokens.filter(
                tags__name__in=tags
            ).distinct()
        
        if is_verified is not None:
            is_verified = is_verified[0]
            is_verified = is_verified.lower()=="true"
            tokens = tokens.filter(
                Q(owner__is_verificated=is_verified) | 
                Q(owners__is_verificated=is_verified)
            ) 

        if currency is not None:
            tokens = tokens.filter(currency__symbol=currency)

        if max_price:
            max_price = Decimal(max_price[0])
            ownerships = Ownership.objects.filter(token__in=tokens)
            ownerships = ownerships.filter(
                Q(currency_price__lte=max_price) |
                Q(currency_minimal_bid__lte=max_price)
            )
            token_ids = list()
            token_ids.extend(ownerships.values_list("token_id", flat=True).distinct())
            token_list = tokens.filter(
                Q(currency_price__lte=max_price) |
                Q(currency_minimal_bid__lte=max_price)
            )
            token_ids.extend(token_list.values_list("id", flat=True).distinct())
            tokens = Token.objects.filter(id__in=token_ids)

        # Below are the tokens in the form of a LIST
        if on_sale is not None:
            on_sale = on_sale[0]
            selling_filter = self.token_selling_filter(on_sale.lower()=="true")
            tokens = filter(selling_filter, tokens)
            tokens = list(tokens)
        
        if order_by is not None:
            order_by = order_by[0]
        reverse = False
        if order_by and order_by.startswith("-"):
            order_by = order_by[1:]
            reverse = True
        
        if order_by == "date":
            tokens = sorted(tokens, key=self.token_sort_updated_at, reverse=reverse)
        elif order_by == "price":
            tokens = sorted(tokens, key=self.token_sort_price, reverse=reverse)
        elif order_by == "likes":
            tokens = sorted(tokens, key=self.token_sort_likes, reverse=reverse)

        page = int(page[0])
        start, end = get_page_slice(page, len(tokens), items_per_page=8)
        return len(tokens), TokenSerializer(tokens[start:end], context={"user": user}, many=True).data

    def collection_search(self, **kwargs):
        words = kwargs.get('words').split(' ')
        page = kwargs.get("page", [1])

        collections = Collection.objects.all()
        collections_count = collections.count()

        for word in words:
            collections = collections.filter(name__icontains=word)

        start, end = get_page_slice(int(page[0]), len(collections))
        return collections_count, CollectionSearchSerializer(collections[start:end]).data
