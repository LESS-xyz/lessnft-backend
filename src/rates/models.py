from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from src.accounts.models import MasterUser
from src.consts import MAX_AMOUNT_LEN


class UsdRate(models.Model):
    """
    Absolutely typical rate app for winter 2021.
    """

    rate = models.DecimalField(
        max_digits=MAX_AMOUNT_LEN, decimal_places=8, blank=True, null=True, default=None
    )
    coin_node = models.CharField(max_length=100)
    symbol = models.CharField(max_length=20, blank=True, null=True, default=None)
    name = models.CharField(max_length=100, blank=True, null=True, default=None)
    image = models.CharField(max_length=500, null=True, blank=True, default=None)
    updated_at = models.DateTimeField(auto_now=True, blank=True, null=True)
    address = models.CharField(max_length=128, blank=True, null=True, default=None)
    decimal = models.PositiveSmallIntegerField(null=True, blank=True, default=None)
    network = models.ForeignKey(
        "networks.Network",
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        default=None,
    )
    fee_discount = models.IntegerField(
        default=100,
        validators=[MaxValueValidator(100), MinValueValidator(1)],
    )

    def __str__(self):
        return self.symbol

    @property
    def get_decimals(self):
        return 10 ** self.decimal

    @property
    def service_fee(self):
        fee = MasterUser.objects.filter(network=self.network).first().commission
        return fee / 100 * self.fee_discount

    @property
    def fee_address(self):
        return MasterUser.objects.filter(network=self.network).first().address

    def set_decimals(self) -> None:
        self.decimal = self.network.contract_call(
            method_type="read",
            contract_type="token",
            address=self.address,
            function_name="decimals",
            input_params=(),
            input_type=(),
            output_types=("uint8",),
        )
        self.save()
