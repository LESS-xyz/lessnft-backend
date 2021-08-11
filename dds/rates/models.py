from django.db import models

from dds.consts import MAX_AMOUNT_LEN


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
        return self.symbol


class CoinPlatform(models.Model):
    """Store platform specific data for coins, but allows direct access to Coin fields."""
    class NetworkEnum(models.TextChoices):
        """Store enum with network name in pair with CoinGecko platform id"""
        BSC = 'binance-smart-chain'
        MATIC = 'polygon-pos'
        ETH = 'ethereum'
    address = models.CharField(max_length=128)
    coin = models.ForeignKey(UsdRate, on_delete=models.CASCADE, related_name='platforms')
    network = models.CharField(max_length=32, choices=NetworkEnum.choices)
    decimal = models.IntegerField(null=True)

    class Meta:
        unique_together = [['address', 'network']]

    def __str__(self):
        return self.address
