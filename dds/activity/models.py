from django.db import models
from dds.accounts.models import AdvUser
from dds.store.models import Token
from dds.settings import ALLOWED_HOSTS
from dds.rates.api import calculate_amount
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

    def get_like(self):
        media = ALLOWED_HOSTS[0] + self.token.media.url

        if self.token.price:
            price = self.token.price / DECIMALS[self.token.currency]
        else:
            price = None

        user_liking = self.user
        token_info = {
            'id': self.token.id,
            'name': self.token.name,
            'standart': self.token.standart,
            'media': media,
            'total_supply': self.token.total_supply,
            'available': self.token.available,
            'price': price,
            'currency': 'WETH' if self.token.currency=='ETH' else self.token.currency,
            'USD_price': calculate_amount(self.token.price, self.token.currency)[0], 
            'owner': self.token.owner.id, 
            'creator': self.token.creator.id,
            'collection': self.token.collection.id, 
            'description': self.token.description, 
            'details': self.token.details,
            'royalty': self.token.creator_royalty, 
            'selling': self.token.selling
        }
        return {'user': user_liking, 'token': token_info}


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
    price = models.DecimalField(max_digits=MAX_AMOUNT_LEN, decimal_places=0, default=None, blank=True, null=True)


class ListingHistory(models.Model):
    token = models.ForeignKey('store.Token', on_delete=models.CASCADE)
    date = models.DateTimeField(auto_now_add=True)
    quantity = models.IntegerField()
    user = models.ForeignKey('accounts.AdvUser', on_delete=models.CASCADE)
    price = models.DecimalField(max_digits=MAX_AMOUNT_LEN, decimal_places=0, default=None, blank=True, null=True)
    method = models.CharField(choices=[('Listing', 'Listing')], default='Listing', max_length=7)


class BidsHistory(models.Model):
    token = models.ForeignKey('store.Token', on_delete=models.CASCADE)
    date = models.DateTimeField() 
    user = models.ForeignKey('accounts.AdvUser', on_delete=models.CASCADE)
    price = models.DecimalField(max_digits=MAX_AMOUNT_LEN, decimal_places=0, default=None, blank=True, null=True)
    method = models.CharField(choices=[('Bet', 'Bet')], default='Bet', max_length=3)
