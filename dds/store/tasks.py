from datetime import datetime, timedelta
from celery import shared_task
from dds.store.models import Token, Status
from dds.store.services.auction import end_auction


@shared_task(name="remove_pending_tokens")
def remove_pending_tokens():
    expiration_date = datetime.today() - timedelta(days=1)
    tokens = Token.objects.filter(
        status__in=(Status.PENDING, Status.FAILED),
        updated_at__lte=expiration_date,
    )
    print(f"Pending {len(tokens)} tokens")
    tokens.delete()


@shared_task(name="end_auction_checker")
def end_auction_checker():
    tokens = Token.objects.committed().filter(
        end_auction__lte=datetime.today(),
    )
    for token in tokens:
        end_auction(token)
