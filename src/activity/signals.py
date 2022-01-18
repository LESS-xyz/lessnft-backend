from django.db.models.signals import post_save
from django.dispatch import receiver

from src.activity.models import TokenHistory
from src.rates.api import calculate_amount


@receiver(post_save, sender=TokenHistory)
def token_history_post_save_dispatcher(sender, instance, created, *args, **kwargs):
    calculate_usd_price(instance, sender)


def calculate_usd_price(token_history, sender):
    """
    Calculate usd price for token history.
    """
    if token_history.price and token_history.currency:
        price = token_history.price * token_history.currency.get_decimals
        token_history.USD_price, _ = calculate_amount(
            price,
            token_history.currency.symbol,
        )
        post_save.disconnect(token_history_post_save_dispatcher, sender=sender)
        token_history.save(
            update_fields=[
                "USD_price",
            ]
        )
        post_save.connect(token_history_post_save_dispatcher, sender=sender)
