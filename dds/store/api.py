import json
import requests
from web3 import Web3
from django.core.exceptions import ObjectDoesNotExist
from django.core.mail import get_connection

from dds.settings import (
    EMAIL_HOST, 
    DDS_HOST_USER,
    DDS_HOST_PASSWORD, 
    EMAIL_PORT, 
    EMAIL_USE_TLS, 
    CAPTCHA_SECRET, 
    CAPTCHA_URL
)
from dds.store.models import Token, Collection
from dds.store.serializers import TokenSerializer, CollectionSearchSerializer


def token_search(words, page):
    words = words.split(' ')

    tokens = Token.objects.all()

    for word in words:
        tokens = tokens.filter(name__icontains=word)

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
