import json
import requests
from decimal import Decimal
from web3 import Web3
from django.core.exceptions import ObjectDoesNotExist
from django.core.mail import get_connection
from django.db.models import Q

from dds.settings import (
    EMAIL_HOST, 
    DDS_HOST_USER,
    DDS_HOST_PASSWORD, 
    EMAIL_PORT, 
    EMAIL_USE_TLS, 
    CAPTCHA_SECRET, 
    CAPTCHA_URL
)
from dds.utilities import get_page_slice
from dds.store.models import Token, Collection, Ownership
from dds.store.serializers import TokenSerializer, CollectionSearchSerializer


def token_selling_filter(is_selling) -> bool:
   def token_filter(token):
       if is_selling:
           return token.is_selling or token.is_auc_selling
       return not token.is_selling and not token.is_auc_selling
   return token_filter


def token_currency_filter(currencies) -> bool:
   def token_filter(token):
        if token.standart=="ERC721":
            return token.currency.symbol in currencies
        return token.ownership_set.filter(
            currency_symbol__in=currencies
        ).exists()
   return token_filter 


def token_sort_price(token, reverse=False):
    if not (token.is_selling or token.is_auc_selling):
        return 0
    if token.standart=="ERC721":
        return token.currency_price if token.currency_price else token.minimal_bid
    owners_price = [owner.get_currency_price for owner in token.ownership_set.all()]    
    if reverse:
        return max(owners_price)
    return min(owners_price)


def token_sort_likes(token, reverse=False):
    return token.useraction_set.filter(method="like").count()


def token_sort_updated_at(token, reverse=False):
    return token.updated_at


def token_search(words, page, **kwargs):
    words = words.split(' ')
    tags = kwargs.get("tags")
    is_verified = kwargs.get("is_verified")
    max_price = kwargs.get("max_price")
    order_by = kwargs.get("order_by")
    on_sale = kwargs.get("on_sale")
    currencies = kwargs.get("currency")

    tokens = Token.objects.all().select_related("currency", "owner")

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

    if currencies is not None:
        currencies = currencies[0].split(",")
        currency_filter = token_currency_filter(currencies)
        tokens = filter(currency_filter, tokens)
        tokens = list(tokens)

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

    page = int(page)
    start, end = get_page_slice(page, len(tokens))
    return TokenSerializer(tokens[start:end], many=True).data


def collection_search(words, page):
    words = words.split(' ')

    collections = Collection.objects.all()

    for word in words:
        collections = collections.filter(name__icontains=word)

    start, end = get_page_slice(page, len(collections))
    return CollectionSearchSerializer(collections[start:end]).data
    

def validate_bid(user, token_id, amount, weth_contract, quantity):
    try:
        token = Token.objects.get(id=token_id)
    except ObjectDoesNotExist:
        return 'Token not found'
    if not token.is_auc_selling:
        return 'token is not set on action'
    if token.minimal_bid and token.minimal_bid > amount:
        return 'Your bid is too low'
    if token.total_supply < quantity:
        return 'Token quantity is lower'
    user_balance = weth_contract.functions.balanceOf(Web3.toChecksumAddress(user.username)).call()
    if user_balance < amount * quantity:
        return 'Your bidding balance is too small'

    return 'OK'

def get_dds_email_connection():
    return get_connection(
        host=EMAIL_HOST,
        port=EMAIL_PORT,
        username=DDS_HOST_USER,
        password=DDS_HOST_PASSWORD,
        use_tls=EMAIL_USE_TLS,
    )

def check_captcha(response):
    print(response)
    data = {
        'secret': CAPTCHA_SECRET,
        'response': response
    }
    response = requests.post(CAPTCHA_URL, data=data)
    print(response)
    answer = json.loads(response.text)
    print(answer)
    return answer['success']
