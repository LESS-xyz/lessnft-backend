from eth_account import Account
from web3 import Web3
from typing import Tuple

from dds.settings import config, PERIODS

def sign_message(type, message):
    message_hash = Web3.soliditySha3(type, message)
    print(f'message_hash: {message_hash}')
    signed = Account.signHash(message_hash, config.PRIV_KEY)
    print(f"signed: {signed}")
    print(f" signature: {signed['signature'].hex()}")
    return signed['signature'].hex()


def get_media_from_ipfs(hash):
    if not hash:
        return None
    return "https://ipfs.io/ipfs/{ipfs}".format(ipfs=hash)


def get_page_slice(page: int, items_length: int = None, items_per_page: int = 50) -> Tuple[int, int]:
    start = (page - 1) * items_per_page
    end = None
    if not items_length or items_length >= page * items_per_page:
        end = page * items_per_page 
    return start, end

def get_periods(*args):
    period = {}
    for key in args:
        period[key] = PERIODS[key]
    return period
