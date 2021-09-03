from django.db import models

from dds.consts import MAX_AMOUNT_LEN

from web3 import Web3, HTTPProvider
from dds.settings import NETWORK_SETTINGS
from contracts import WETH_ABI


class UsdRate(models.Model):
    '''
    Absolutely typical rate app for winter 2021.
    '''
    rate = models.DecimalField(max_digits=MAX_AMOUNT_LEN, decimal_places=8)
    coin_node = models.CharField(max_length=100)
    symbol = models.CharField(max_length=20)
    name = models.CharField(max_length=100)
    image = models.CharField(max_length=500, null=True)
    updated_at = models.DateTimeField(auto_now=True)
    address = models.CharField(max_length=128)
    decimal = models.PositiveSmallIntegerField(null=True)
    network = models.ForeignKey('networks.Network', on_delete=models.CASCADE)

    def __str__(self):
        return self.symbol

    @property
    def get_decimals(self) -> None:
        return 10 ** self.decimal

    def set_decimals(self) -> None:
        web3 = Web3(HTTPProvider(NETWORK_SETTINGS['ETH']['endpoint']))
        address = web3.toChecksumAddress(self.address)
        contract = web3.eth.contract(address=address, abi=WETH_ABI)
        self.decimal = contract.functions.decimals().call()
        self.save()
