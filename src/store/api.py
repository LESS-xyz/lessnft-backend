import json

import requests
from django.core.exceptions import ObjectDoesNotExist
from django.core.mail import get_connection

from src.settings import config
from src.store.models import Token


def validate_bid(user, token_id, amount, quantity):
    try:
        token = Token.objects.committed().get(id=token_id)
    except ObjectDoesNotExist:
        return "Token not found"
    amount = amount * token.currency.get_decimals
    if not token.is_auc_selling and not token.is_timed_auc_selling:
        return "token is not set on auction"
    if token.standart=="ERC721" and token.currency_minimal_bid > amount:
        return "Your bid is too low"
    if (
        token.standart == "ERC721"
        and token.get_highest_bid()
        and token.get_highest_bid() > amount
    ):
        return "Your bid is too low"
    if token.total_supply < quantity:
        return "Token quantity is lower"

    user_balance = token.currency.network.contract_call(
        method_type="read",
        contract_type="token",
        address=token.currency.address,
        function_name="balanceOf",
        input_params=(token.collection.network.wrap_in_checksum(user.username),),
        input_type=("address",),
        output_types=("uint256",),
    )

    if user_balance < amount * quantity:
        return "Your bidding balance is too small"

    return "OK"


def get_email_connection():
    return get_connection(
        host=config.EMAIL_HOST,
        port=config.EMAIL_PORT,
        username=config.HOST_USER,
        password=config.HOST_PASSWORD,
        use_tls=config.EMAIL_USE_TLS,
    )


def check_captcha(response):
    data = {"secret": config.CAPTCHA_SECRET, "response": response}
    response = requests.post(config.CAPTCHA_URL, data=data)
    answer = json.loads(response.text)
    return answer["success"]
