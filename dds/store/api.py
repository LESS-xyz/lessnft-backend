import json

import requests
from dds.rates.api import calculate_amount
from dds.settings import config
from dds.store.models import Token
from django.core.exceptions import ObjectDoesNotExist
from django.core.mail import get_connection


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
    prices = [calculate_amount(owner.get_currency_price, currency)[0] for owner in owners if owner.get_currency_price]
    if reverse:
        return max(prices)
    return min(prices)


def token_sort_likes(token, reverse=False):
    return token.useraction_set.filter(method="like").count()


def token_sort_updated_at(token, reverse=False):
    return token.updated_at


def validate_bid(user, token_id, amount, quantity):
    try:
        token = Token.objects.committed().get(id=token_id)
    except ObjectDoesNotExist:
        return 'Token not found'
    amount = amount * token.currency.get_decimals
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
