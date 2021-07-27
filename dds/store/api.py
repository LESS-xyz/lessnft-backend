import json
import ipfshttpclient
import requests
import multiaddr
from web3 import Web3, HTTPProvider
from django.core.exceptions import ObjectDoesNotExist
from django.core.mail import get_connection

from dds.settings import (
    ALLOWED_HOSTS, 
    SORT_STATUSES, 
    WETH_CONTRACT, 
    NETWORK_SETTINGS,
    EMAIL_HOST, 
    DDS_HOST_USER, 
    DDS_HOST_PASSWORD, 
    DDS_MAIL, 
    EMAIL_PORT, 
    EMAIL_USE_TLS,
    CAPTCHA_SECRET,
    CAPTCHA_URL
)
from dds.consts import DECIMALS
from dds.rates.api import calculate_amount
from dds.store.models import Token, Collection, Ownership
from dds.utilities import get_media_if_exists


def token_search(words, page):
    words = words.split(' ')

    tokens = Token.objects.all()

    for word in words:
        tokens = tokens.filter(name__icontains=word)

    search_result = []
    start = (page - 1) * 50
    end = page * 50 if len(tokens) >= page * 50 else None

    for token in tokens[start: end]:
        try:
            avatar = ALLOWED_HOSTS[0] + token.media.url
        except ValueError:
            avatar = ''
        token_owners = []
        if token.standart == 'ERC1155':
            owners = token.owners.all()
            available = 0
            for owner in owners:
                holder = {
                    'id': owner.id,
                    'name': owner.get_name(),
                    'avatar': get_media_if_exists(owner, 'avatar'),
                    'quantity': Ownership.objects.get(owner=owner, token=token).quantity
                    }
                token_owners.append(holder)
                if Ownership.objects.get(owner=owner, token=token).selling:
                    available += Ownership.objects.get(owner=owner, token=token).quantity
        else:
            owner = {
                'id': token.owner.id,
                'name': token.owner.get_name(),
                'avatar': get_media_if_exists(token.owner, 'avatar'),
                }
            token_owners.append(owner)
            if token.selling:
                available = 1
            else:
                available = 0

        search_result.append({
            'id': token.id,
            'name': token.name,
            'standart': token.standart,
            'media': avatar,
            'total_supply': token.total_supply,
            'available': available,
            'price': token.price / DECIMALS[token.currency] if token.price else None,
            'currency': token.currency,
            'USD_price': calculate_amount(token.price, token.currency)[0] if token.price else None,
            'owners': token_owners,
            'creator': {
                'id': token.creator.id,
                'name': token.creator.get_name(),
                'avatar': get_media_if_exists(token.creator, 'avatar')
            },
            'collection': {
                'id': token.collection.id,
                'avatar': get_media_if_exists(token.collection, 'avatar'),
                'name': token.collection.name
            },
            'description': token.description,
            'details': token.details,
            'royalty': token.creator_royalty,
            'selling': token.selling
        })

    return search_result


def collection_search(words, page):
    words = words.split(' ')

    collections = Collection.objects.all()

    for word in words:
        collections = collections.filter(name__icontains=word)

    search_result = []
    start = (page - 1) * 50
    end = page * 50 if len(collections) >= page * 50 else None

    for collection in collections[start: end]:
        try:
            avatar = ALLOWED_HOSTS[0] + collection.avatar.url
        except ValueError:
            avatar = ''

        tokens = Token.objects.filter(collection=collection).order_by(SORT_STATUSES['recent'])[:6]
        token_list = []

        for token in tokens:
            token_media = get_media_if_exists(token, 'media')

            token_list.append(token_media)

        search_result.append({
            'id': collection.id,
            'name': collection.name,
            'avatar': avatar,
            'tokens': token_list
        })

    return search_result

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
