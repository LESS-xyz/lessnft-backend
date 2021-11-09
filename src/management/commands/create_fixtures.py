from src.accounts.models import MasterUser
from src.networks.models import Network
from src.settings import config
from src.store.models import UsdRate
from django.core.management.base import BaseCommand
from django_celery_beat.models import IntervalSchedule, PeriodicTask


class Command(BaseCommand):
    """Provide initial db fixtures from config with 'manage.py create_fixtures.py'"""
    def handle(self, *args, **options):
        help = 'Create initial fixtures for Networks, Usd rates and Master user'

        """Create Network objects"""
        for network in config.NETWORKS:
            Network.objects.get_or_create(
                name=network.name,
                needs_middlware=network.needs_middlware,
                native_symbol=network.native_symbol,
                endpoint=network.endpoint,
                fabric721_address=network.fabric721_address,
                fabric1155_address=network.fabric1155_address,
                exchange_address=network.exchange_address,
                network_type=network.network_type
                )

        """Create UsdRates objects"""
        for usd_rate in config.USD_RATES:
            obj, created = UsdRate.objects.get_or_create(
                coin_node=usd_rate.coin_node,
                symbol=usd_rate.symbol,
                name=usd_rate.name,
                image=usd_rate.image,
                address=usd_rate.address,
                network=usd_rate.network,
                fee_discount=usd_rate.fee_discount
                )
            if created:
                obj.set_decimals()

        """Create Master User object"""
        MasterUser.objects.get_or_create(
            address=config.MASTER_USER.address,
            network=config.MASTER_USER.network,
            commission=config.MASTER_USER.commission
            )
        
        """Create Intervals for Celery"""
        for interval in config.INTERVALS:
            IntervalSchedule.objects.get_or_create(
                every=interval.every,
                period=interval.period
            )
        
        """Create Periodic task for Celery"""
        for periodic_task in config.PERIODIC_TASKS:
            PeriodicTask.objects.get_or_create(
                name=periodic_task.name,
                task=periodic_task.task,
                interval=periodic_task.interval,
                enabled=True
            )
