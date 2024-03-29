from django.core.management.base import BaseCommand
from django_celery_beat.models import IntervalSchedule, PeriodicTask

from src.accounts.models import MasterUser
from src.networks.models import Network, Provider
from src.settings import config
from src.store.models import UsdRate


class Command(BaseCommand):
    """Provide initial db fixtures from config with 'manage.py create_fixtures.py'"""

    def handle(self, *args, **options):
        help = "Create initial fixtures for Networks, Usd rates and Master user"  # noqa F841

        """Create Network objects"""
        for network in config.NETWORKS:
            Network.objects.get_or_create(
                name=network.name,
                needs_middleware=network.needs_middleware,
                native_symbol=network.native_symbol,
                fabric721_address=network.fabric721_address,
                fabric1155_address=network.fabric1155_address,
                exchange_address=network.exchange_address,
                network_type=network.network_type,
            )

        """Create Provider objects"""
        for provider in config.PROVIDERS:
            Provider.objects.get_or_create(
                endpoint=provider.endpoint,
                network=Network.objects.get(name__iexact=provider.network),
            )

        """Create UsdRates objects"""
        for usd_rate in config.USD_RATES:
            UsdRate.objects.get_or_create(
                coin_node=usd_rate.coin_node,
                symbol=usd_rate.symbol,
                name=usd_rate.name,
                image=usd_rate.image,
                address=usd_rate.address,
                network=Network.objects.get(name__iexact=usd_rate.network),
                fee_discount=usd_rate.fee_discount,
                decimal=usd_rate.decimal,
            )

        """Create Master User objects"""
        for master_user in config.MASTER_USER:
            instance = MasterUser.objects.get(
                network=Network.objects.get(name__iexact=master_user.network),
            )
            instance.address = master_user.address
            instance.commission = master_user.commission
            instance.save()

        """Create Intervals for Celery"""
        for interval in config.INTERVALS:
            IntervalSchedule.objects.get_or_create(
                pk=interval.pk,
                every=interval.every,
                period=getattr(IntervalSchedule, interval.period),
            )

        """Create Periodic task for Celery"""
        for periodic_task in config.PERIODIC_TASKS:
            PeriodicTask.objects.get_or_create(
                name=periodic_task.name,
                task=periodic_task.task,
                interval=IntervalSchedule.objects.get(id=periodic_task.interval),
                enabled=True,
            )
