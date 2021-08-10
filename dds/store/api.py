import json
import requests
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
from dds.store.models import Token, Collection, Ownership
from dds.store.serializers import TokenSerializer, CollectionSearchSerializer


def token_sort_price(token, reverse=False):
    if token.standart=="ERC721":
        return token.price if token.price else token.minimal_bid
    if reverse:
        return max(token.ownership_set.values_list("get_price", flat=True))
    return min(token.ownership_set.values_list("get_price", flat=True))


def token_sort_likes(token, reverse=False):
    return token.useraction_set.filter(method="like").count()


def token_search(words, page, **kwargs):
    # TODO: move filters to custom QuerySet
    words = words.split(' ')
    is_verified = kwargs.get("is_verified")
    max_price = kwargs.get("max_price")
    order_by = kwargs.get("order_by")
    on_sale = kwargs.get("on_sale")

    tokens = Token.objects.all()

    for word in words:
        tokens = tokens.filter(name__icontains=word)
    
    if is_verified is not None:
        is_verified = is_verified[0]
        tokens = tokens.filter(
            Q(owner__is_verificated=is_verified) | 
            Q(owners__is_verificated=is_verified)
        ) 

    if on_sale:
        new_tokens = set()
        for token in tokens:
            if token.standart=="ERC721":
                if token.is_selling or token.is_auc_selling:
                    new_tokens.add(token)
            elif Ownership.objects.filter(token=token).filter(
                Q(is_selling=True) |
                Q(is_auc_selling=True)
            ).exists():
                new_tokens.add(token)
        tokens = list(new_tokens)

    if max_price:
        ...
    
    if order_by is not None:
        order_by = order_by[0]
    reverse = False
    if order_by.startswith("-"):
        order_by = order_by[1:]
        reverse = True
    
    if order_by == "date":
        tokens = tokens.order_by("updated_at")
        if reverse:
            tokens = tokens.reverse()
    elif order_by == "price":
        tokens = sorted(tokens, key=token_sort_price, reverse=reverse)
    elif order_by == "likes":
        tokens = sorted(tokens, key=token_sort_likes, reverse=reverse)

    page = int(page)
    start = (page - 1) * 50
    end = page * 50 if len(tokens) >= page * 50 else None
    return TokenSerializer(tokens[start:end], many=True).data


def collection_search(words, page):
    words = words.split(' ')

    collections = Collection.objects.all()

    for word in words:
        collections = collections.filter(name__icontains=word)

    start = (page - 1) * 50
    end = page * 50 if len(collections) >= page * 50 else None
    return CollectionSearchSerializer(collections[start:end]).data
    

def validate_bid(user, token_id, amount, weth_contract, quantity):
    try:
        token = Token.objects.get(id=token_id)
    except ObjectDoesNotExist:
        return 'Token not found'
    if token.sell_status != token.SellStatus.AUCTION:
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
