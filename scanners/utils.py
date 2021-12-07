import os
import sys
import time
import traceback

from scanners.eth.scanner import Scanner as EthereumScanner
from scanners.tron.scanner import Scanner as TronScanner
from src.networks.models import Network, Types


def get_scanner(network, contract_type=None, contract=None):
    # TODO: refactor
    if network.network_type.lower() == Types.ethereum.lower():
        return EthereumScanner(network, contract_type, contract=contract)
    if network.network_type.lower() == Types.tron.lower():
        return TronScanner(network, contract_type, contract=contract)
    else:
        print(network.network_type)
        print(Types.ethereum)
        print(network, contract_type, contract)


def never_fall(func):
    def wrapper(*args, **kwargs):
        while True:
            try:
                func(*args, **kwargs)
            except Exception as e:
                print(
                    "\n".join(traceback.format_exception(*sys.exc_info())),
                    flush=True,
                )
                time.sleep(60)

    return wrapper
