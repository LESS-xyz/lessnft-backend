from django.utils import timezone
from django.core.management.base import BaseCommand
from django_celery_beat.models import PeriodicTask, IntervalSchedule


class Command(BaseCommand):
    help = "Start periodic tasks for remove pending tokens"

    def handle(self, *args, **options):
        PeriodicTask.objects.create(
            name="Remove pending tokens",
            task="remove_pending_tokens",
            interval=IntervalSchedule.objects.get_or_create(every=10, period="seconds")[
                0
            ],
            start_time=timezone.now(),
        )
        print("Periodic task created!")
