from django.db import models

from dds.consts import MAX_AMOUNT_LEN


class UserAction(models.Model):
    whom_follow = models.ForeignKey(
        'accounts.AdvUser',
        related_name="following",
        on_delete=models.CASCADE,
        blank=True,
        null=True
    )
    user = models.ForeignKey(
        'accounts.AdvUser',
        related_name="followers",
        on_delete=models.CASCADE
    )
    date = models.DateTimeField(auto_now_add=True, db_index=True)
    method = models.CharField(
        choices=[('like', 'like'), ('follow', 'follow')],
        max_length=6,
        default='follow'
    )
    token = models.ForeignKey(
        'store.Token',
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        default=None
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['whom_follow', 'user'],  name='unique_followers'),
            models.UniqueConstraint(fields=['user', 'token'], name='unique_likes')
        ]

        ordering = ["-date"]


class TokenHistory(models.Model):
    token = models.ForeignKey('store.Token', on_delete=models.CASCADE)
    date = models.DateTimeField(auto_now_add=True)
    tx_hash = models.CharField(max_length=200)
    method = models.CharField(
        max_length=10,
        choices=[('Transfer', 'Transfer'), ('Buy', 'Buy'), ('Mint', 'Mint'), ('Burn', 'Burn')],
        default='Transfer'
    )
    new_owner = models.ForeignKey(
        'accounts.AdvUser',
        on_delete=models.DO_NOTHING,
        blank=True,
        null=True,
        related_name='new_owner'
    )
    old_owner = models.ForeignKey(
        'accounts.AdvUser',
        on_delete=models.DO_NOTHING,
        blank=True,
        null=True,
        related_name='old_owner'
    )
    price = models.DecimalField(max_digits=MAX_AMOUNT_LEN, decimal_places=18, default=None, blank=True, null=True)
    currency = models.ForeignKey('rates.UsdRate', on_delete=models.PROTECT, null=True, blank=True, default=None)


class ListingHistory(models.Model):
    token = models.ForeignKey('store.Token', on_delete=models.CASCADE)
    date = models.DateTimeField(auto_now_add=True)
    quantity = models.IntegerField()
    user = models.ForeignKey('accounts.AdvUser', on_delete=models.CASCADE)
    price = models.DecimalField(max_digits=MAX_AMOUNT_LEN, decimal_places=18, default=None, blank=True, null=True)
    currency = models.ForeignKey('rates.UsdRate', on_delete=models.PROTECT, null=True, blank=True, default=None)
    method = models.CharField(choices=[('Listing', 'Listing')], default='Listing', max_length=7)


class BidsHistory(models.Model):
    token = models.ForeignKey('store.Token', on_delete=models.CASCADE)
    date = models.DateTimeField()
    user = models.ForeignKey('accounts.AdvUser', on_delete=models.CASCADE)
    price = models.DecimalField(max_digits=MAX_AMOUNT_LEN, decimal_places=18, default=None, blank=True, null=True)
    currency = models.ForeignKey('rates.UsdRate', on_delete=models.PROTECT, null=True, blank=True, default=None)
    method = models.CharField(choices=[('Bet', 'Bet')], default='Bet', max_length=3)
