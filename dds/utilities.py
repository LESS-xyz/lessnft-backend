from datetime import datetime
from os.path import splitext
from eth_account import Account
from dds.settings import PRIV_KEY
from web3 import Web3

from dds.settings import ALLOWED_HOSTS

def get_timestamp_path(instance, filename):
    return '%s%s' % (datetime.now().timestamp(), splitext(filename)[1])

def sign_message(type, message):
    message_hash = Web3.soliditySha3(type, message)
    signed = Account.signHash(message_hash, PRIV_KEY)
    print(signed['signature'].hex())
    return signed['signature'].hex()

def get_media_if_exists(queryset, field):
    try:
        avatar = ALLOWED_HOSTS[0] + getattr(queryset, field).url
    except ValueError:
        avatar = ''

    return avatar
