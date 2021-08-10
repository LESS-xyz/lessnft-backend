from typing import TYPE_CHECKING

from django.db import models
from web3 import Web3
from web3.middleware import geth_poa_middleware

from contracts import (
    WETH_CONTRACT,
    EXCHANGE,
    ERC721_MAIN,
    ERC721_FABRIC,
    ERC1155_MAIN,
    ERC1155_FABRIC,
)


if TYPE_CHECKING:
    from web3.contract import Contract
    from web3.types import ABI


class Network(models.Model):
    """Represent different networks as different blockchains, in witch we have our contracts."""
    name = models.CharField(max_length=100)
    erc721_main_address = models.CharField(max_length=128)
    erc1155_main_address = models.CharField(max_length=128)
    erc721_fabric_address = models.CharField(max_length=128)
    erc1155_fabric_address = models.CharField(max_length=128)
    exchange_address = models.CharField(max_length=128)
    weth_address = models.CharField(max_length=128)
    endpoint = models.CharField(max_length=256)
    needs_middleware = models.BooleanField(default=False)
    native_symbol = models.CharField(max_length=10, default='BNB')

    def get_web3_connection(self) -> 'Web3':
        web3 = Web3(Web3.HTTPProvider(self.endpoint))
        if self.needs_middleware:
            web3.middleware_onion.inject(geth_poa_middleware, layer=0)
        return web3

    def _get_contract_by_abi(self, abi: 'ABI', address: str = None) -> ('Web3', 'Contract'):
        web3 = self.get_web3_connection()
        if address:
            address = web3.toChecksumAddress(address)
        contract = web3.eth.contract(address=address, abi=abi)
        return web3, contract

    def get_erc721_main_contract(self) -> ('Web3', 'Contract'):
        return self._get_contract_by_abi(ERC721_MAIN, self.erc721_main_address)

    def get_erc721_fabric_contract(self) -> ('Web3', 'Contract'):
        return self._get_contract_by_abi(ERC721_FABRIC, self.erc721_fabric_address)

    def get_erc1155_main_contract(self) -> ('Web3', 'Contract'):
        return self._get_contract_by_abi(ERC1155_MAIN, self.erc1155_main_address)

    def get_erc1155_fabric_contract(self) -> ('Web3', 'Contract'):
        return self._get_contract_by_abi(ERC1155_FABRIC, self.erc1155_fabric_address)

    def get_exchange_contract(self) -> ('Web3', 'Contract'):
        return self._get_contract_by_abi(EXCHANGE, self.exchange_address)

    def get_weth_contract(self) -> ('Web3', 'Contract'):
        return self._get_contract_by_abi(WETH_CONTRACT, self.weth_address)
