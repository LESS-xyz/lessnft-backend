from django.db import models

from dds.consts import MAX_AMOUNT_LEN
from dds.networks.models import Network


class UsdRate(models.Model):
    '''
    Absolutely typical rate app for winter 2021.
    '''
    rate = models.DecimalField(max_digits=MAX_AMOUNT_LEN, decimal_places=8)
    coin_node = models.CharField(max_length=100, unique=True)
    symbol = models.CharField(max_length=20)
    name = models.CharField(max_length=100)
    image = models.CharField(max_length=500, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.currency


class CoinPlatform(models.Model):
    """Store platform specific data for coins, but allows direct access to Coin fields."""
    address = models.CharField(max_length=128)
    coin = models.ForeignKey(UsdRate, on_delete=models.CASCADE, related_name='platforms')
    network = models.ForeignKey(Network, on_delete=models.CASCADE, related_name='platforms')
    decimal = models.IntegerField(null=True)

    class Meta:
        unique_together = [['address', 'network']]

    def __str__(self):
        return self.address

    def get_network(self) -> 'Network':
        network_model = apps.get_model('networks', 'Network')
        network = network_model.objects.filter(name=self.platform).first()
        return network

    def check_decimals(self) -> None:
        """Obtain decimals number from token contract and save in current model."""
        network = self.get_network()
        web3, contract = network.get_bep20_contract(self.address)
        decimal = contract.functions.decimals().call()
        self.decimal = decimal
        self.save()
