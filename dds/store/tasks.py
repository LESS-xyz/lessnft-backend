from datetime import datetime, timedelta
from celery import shared_task
from dds.store.models import Token, Status


@shared_task(name="remove_pending_tokens")
def remove_pending_tokens():
    expiration_date = datetime.today() - timedelta(days=1)
    tokens = Token.objects.filter(
        status__in=(Status.PENDING, Status.FAILED),
        updated_at__lte=expiration_date,
    )
    print(f"Pending {len(tokens)} tokens")
    tokens.delete()
