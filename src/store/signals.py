import random

from django.core.exceptions import ValidationError
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from src.accounts.models import DefaultAvatar
from src.store.models import Collection, Ownership, Token


@receiver(post_save, sender=Collection)
def collection_post_save_dispatcher(sender, instance, created, *args, **kwargs):
    update_delete_status(instance)
    set_default_avatar(instance, created)


@receiver(pre_save, sender=Token)
def token_pre_save_dispatcher(sender, instance, *args, **kwargs):
    unique_name_for_network_validator(instance)


@receiver(post_save, sender=Ownership)
def ownership_post_save_dispatcher(sender, instance, created, *args, **kwargs):
    recalculate_token_sell_status(instance)


def unique_name_for_network_validator(token):
    """
    Raise exception if token with same name and network exists.
    """
    matching_token = Token.objects.filter(
        name=token.name,
        collection__network=token.collection.network,
    )
    if token.id:
        matching_token = matching_token.exclude(id=token.id)
    if matching_token.exists():
        raise ValidationError("Name is occupied")


def recalculate_token_sell_status(ownership):
    """
    Recalculate 1155 token fields: selling, currency, currency_price.
    """
    token = ownership.token
    if not token.ownership_set.filter(selling=True).exists():
        token.selling = False
        token.currency_minimal_bid = None
        token.currency_price = None
        token.currency = None
    else:
        token.selling = True
        ownerships = token.ownership_set.filter(
            selling=True,
        )
        ownerships = list(ownerships)
        ownerships.sort(key=lambda owner: owner.usd_price)
        if ownerships:
            token.currency_price = ownerships[0].currency_price or ownerships[0].currency_minimal_bid
            token.currency = ownerships[0].currency
    token.save(update_fields=["selling", "currency_price", "currency"])


def update_delete_status(collection):
    """
    If collection DELETED, change collection tokens on DELETED.
    """
    if collection.deleted:
        collection.token_set.update(deleted=True)


def set_default_avatar(collection, created):
    """
    Set default avatar for collection.
    """
    if created and not collection.avatar_ipfs:
        default_avatars = DefaultAvatar.objects.all().values_list("image", flat=True)
        if default_avatars:
            collection.avatar_ipfs = random.choice(default_avatars)
            collection.save()
