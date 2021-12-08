import logging
from web3 import Web3

from tronapi import Tron
from tronapi.common.account import Account
from rest_framework.exceptions import ValidationError
from ethereum.utils import ecrecover_to_pub, sha3
from eth_utils.hexadecimal import encode_hex, decode_hex, add_0x_prefix
from eth_account.messages import defunct_hash_message
from eth_hash.auto import keccak as keccak_256


def valid_metamask_message(address, message, signature):
    try:
        address = Web3.toChecksumAddress(address)
        r = int(signature[0:66], 16)
        s = int(add_0x_prefix(signature[66:130]), 16)
        v = int(add_0x_prefix(signature[130:132]), 16)
        if v not in (27, 28):
            v += 27

        message_hash = defunct_hash_message(text=message)
        pubkey = ecrecover_to_pub(decode_hex(message_hash.hex()), v, r, s)
        signer_address = encode_hex(sha3(pubkey)[-20:])

        """
        message_hash = encode_defunct(text=message)
        signer_address = Account.recover_message(message_hash, vrs=(v, r, s))
        """
        logging.info(f"matching {signer_address}, {address}")

        if signer_address.lower() != address.lower():
            raise ValidationError({"result": "Incorrect signature"}, code=400)
        return True
    except ValueError:
        tron = Tron()
        message_hash = tron.toHex(text=message)
        header = "\x19TRON Signed Message:\n32"
        message_hash_keccak = keccak_256(
            header.encode("utf-8") + bytes.fromhex(message_hash[2:])
        )
        signer_address = Account.recover_hash(message_hash_keccak.hex(), signature)
        tron_address = "41" + signer_address[2:]
        signer_address = tron.address.from_hex(tron_address).decode()

        logging.info(f"matching {signer_address}, {address}")

        if signer_address.lower() != address.lower():
            raise ValidationError({"result": "Incorrect signature"}, code=400)
        return True
