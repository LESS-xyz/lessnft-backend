from typing import TYPE_CHECKING

from django.db import models
from web3 import Web3
from web3.middleware import geth_poa_middleware

from contracts import (
    EXCHANGE,
    WETH_ABI,
    ERC721_MAIN,
    ERC721_FABRIC,
    ERC1155_MAIN,
    ERC1155_FABRIC,
)


if TYPE_CHECKING:
    from web3.contract import Contract
    from web3.types import ABI


class Network(models.Model):
    """
    Represent different networks as different blockchains, 
    in witch we have our contracts.
    """
    name = models.CharField(max_length=100)
    needs_middleware = models.BooleanField(default=False)
    native_symbol = models.CharField(max_length=10, blank=True, null=True, default=None)
    endpoint = models.CharField(max_length=256)
    fabric721_address = models.CharField(max_length=128)
    fabric1155_address = models.CharField(max_length=128)
    exchange_address = models.CharField(max_length=128)

    def __str__(self):
        return self.name

    def get_web3_connection(self) -> "Web3":
        web3 = Web3(Web3.HTTPProvider(self.endpoint))
        if self.needs_middleware:
            web3.middleware_onion.inject(geth_poa_middleware, layer=0)
        return web3

    def _get_contract_by_abi(self, abi: "ABI", address: str = None) -> ("Web3", "Contract"):
        web3 = self.get_web3_connection()
        if address:
            address = web3.toChecksumAddress(address)
        contract = web3.eth.contract(address=address, abi=abi)
        return web3, contract

    def get_exchage_contract(self) -> ("Web3", "Contract"):
        return self._get_contract_by_abi(EXCHANGE, self.exchange_address)

    def get_erc721fabric_contract(self) -> ("Web3", "Contract"):
        return self._get_contract_by_abi(ERC721_FABRIC, self.fabric721_address)

    def get_erc1155fabric_contract(self) -> ("Web3", "Contract"):
        return self._get_contract_by_abi(ERC1155_FABRIC, self.fabric1155_address)

    def get_erc721main_contract(self, address: str = None) -> ("Web3", "Contract"):
        return self._get_contract_by_abi(ERC721_MAIN, address)

    def get_erc1155main_contract(self, address: str = None) -> ("Web3", "Contract"):
        return self._get_contract_by_abi(ERC1155_MAIN, address)

    def get_token_contract(self, address: str = None) -> ("Web3", "Contract"):
        return self._get_contract_by_abi(WETH_ABI, address)
