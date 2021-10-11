import json
import requests
from web3 import Web3
from django.core.exceptions import ObjectDoesNotExist
from django.core.mail import get_connection
from django.db.models import Q

from dds.settings import config
from dds.store.models import Token


def validate_bid(user, token_id, amount, token_contract, quantity):
    try:
        token = Token.token_objects.committed().get(id=token_id)
    except ObjectDoesNotExist:
        return 'Token not found'
    if not token.is_auc_selling:
        return 'token is not set on action'
    if token.get_highest_bid() and token.get_highest_bid() > amount:
        return 'Your bid is too low'
    if token.total_supply < quantity:
        return 'Token quantity is lower'
    user_balance = token_contract.functions.balanceOf(Web3.toChecksumAddress(user.username)).call()
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
