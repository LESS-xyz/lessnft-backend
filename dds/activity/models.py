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
    is_viewed = models.BooleanField(default=False)

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
    is_viewed = models.BooleanField(default=False)


class ListingHistory(models.Model):
    token = models.ForeignKey('store.Token', on_delete=models.CASCADE)
    date = models.DateTimeField(auto_now_add=True)
    quantity = models.IntegerField()
    user = models.ForeignKey('accounts.AdvUser', on_delete=models.CASCADE)
    price = models.DecimalField(max_digits=MAX_AMOUNT_LEN, decimal_places=18, default=None, blank=True, null=True)
    method = models.CharField(choices=[('Listing', 'Listing')], default='Listing', max_length=7)
    is_viewed = models.BooleanField(default=False)


class BidsHistory(models.Model):
    token = models.ForeignKey('store.Token', on_delete=models.CASCADE)
    date = models.DateTimeField()
    user = models.ForeignKey('accounts.AdvUser', on_delete=models.CASCADE)
    price = models.DecimalField(max_digits=MAX_AMOUNT_LEN, decimal_places=18, default=None, blank=True, null=True)
    method = models.CharField(choices=[('Bet', 'Bet')], default='Bet', max_length=3)
    is_viewed = models.BooleanField(default=False)


class UserStat(models.Model):
    user = models.OneToOneField('accounts.AdvUser', on_delete=models.CASCADE)
    buyer_day = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True, default=None)
    buyer_week = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True, default=None)
    buyer_month = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True, default=None)
    seller_day = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True, default=None)
    seller_week = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True, default=None)
    seller_month = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True, default=None)

    def __str__(self):
        return self.user.get_name()
