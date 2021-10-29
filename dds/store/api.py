import json
import requests
from web3 import Web3
from django.core.exceptions import ObjectDoesNotExist
from django.core.mail import get_connection
from django.db.models import Q

from dds.settings import config
from dds.store.models import Token


def token_selling_filter(is_selling) -> bool:
   def token_filter(token):
       if is_selling:
           return token.is_selling or token.is_auc_selling
       return not token.is_selling and not token.is_auc_selling
   return token_filter


def token_sort_price(token, reverse=False):
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


def token_sort_likes(token, reverse=False):
    return token.useraction_set.filter(method="like").count()


def token_sort_updated_at(token, reverse=False):
    return token.updated_at


def token_search(words, **kwargs):
    words = words.split(' ')
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
    tokens = Token.objects.committed().network(network[0]).select_related("currency", "owner")
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
        selling_filter = token_selling_filter(on_sale.lower()=="true")
        tokens = filter(selling_filter, tokens)
        tokens = list(tokens)
    
    if order_by is not None:
        order_by = order_by[0]
    reverse = False
    if order_by and order_by.startswith("-"):
        order_by = order_by[1:]
        reverse = True

    if order_by == "date":
        tokens = sorted(tokens, key=token_sort_updated_at, reverse=reverse)
    elif order_by == "price":
        tokens = sorted(tokens, key=token_sort_price, reverse=reverse)
    elif order_by == "likes":
        tokens = sorted(tokens, key=token_sort_likes, reverse=reverse)

    page = int(page[0])
    start, end = get_page_slice(page, len(tokens), items_per_page=8)
    return len(tokens), TokenSerializer(tokens[start:end], context={"user": user}, many=True).data


def collection_search(words, page):
    words = words.split(' ')

    collections = Collection.objects.committed()

    for word in words:
        collections = collections.filter(name__icontains=word)

    start, end = get_page_slice(page, len(collections))
    return CollectionSearchSerializer(collections[start:end]).data
    

def validate_bid(user, token_id, amount, quantity):
    try:
        token = Token.objects.committed().get(id=token_id)
    except ObjectDoesNotExist:
        return 'Token not found'
    if not token.is_auc_selling:
        return 'token is not set on action'
    if token.get_highest_bid() and token.get_highest_bid() > amount:
        return 'Your bid is too low'
    if token.total_supply < quantity:
        return 'Token quantity is lower'

    user_balance = token.currency.network.contract_call(
            method_type='read', 
            contract_type='token',
            address=token.currency.address, 
            function_name='balanceOf',
            input_params=(user.username,),
            input_type=('address',),
            output_types=('uint256',),
    )

    if user_balance < amount * quantity:
        return 'Your bidding balance is too small'

    return 'OK'

def get_dds_email_connection():
    return get_connection(
        host=config.EMAIL_HOST,
        port=config.EMAIL_PORT,
        username=config.DDS_HOST_USER,
        password=config.DDS_HOST_PASSWORD,
        use_tls=config.EMAIL_USE_TLS,
    )

def check_captcha(response):
    data = {
        'secret': config.CAPTCHA_SECRET,
        'response': response
    }
    response = requests.post(config.CAPTCHA_URL, data=data)
    answer = json.loads(response.text)
    return answer['success']
