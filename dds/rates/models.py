from django.db import models

from dds.consts import MAX_AMOUNT_LEN

from web3 import Web3, HTTPProvider
from contracts import WETH_ABI


class UsdRate(models.Model):
    '''
    Absolutely typical rate app for winter 2021.
    '''
    rate = models.DecimalField(max_digits=MAX_AMOUNT_LEN, decimal_places=8, blank=True, null=True, default=None)
    coin_node = models.CharField(max_length=100)
    symbol = models.CharField(max_length=20, blank=True, null=True, default=None)
    name = models.CharField(max_length=100, blank=True, null=True, default=None)
    image = models.CharField(max_length=500, null=True, blank=True, default=None)
    updated_at = models.DateTimeField(auto_now=True, blank=True, null=True)
    address = models.CharField(max_length=128, blank=True, null=True, default=None)
    decimal = models.PositiveSmallIntegerField(null=True, blank=True, default=None)
    network = models.ForeignKey('networks.Network', on_delete=models.CASCADE, blank=True, null=True, default=None)

    def __str__(self):
        return self.symbol

    @property
    def get_decimals(self) -> None:
        return 10 ** self.decimal

    def set_decimals(self) -> None:
        address = Web3.toChecksumAddress(self.address)
        web3, contract = self.network.get_token_contract(address)
        self.decimal = contract.functions.decimals().call()
        self.save()
