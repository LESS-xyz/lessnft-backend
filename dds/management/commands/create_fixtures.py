from django.core.management.base import BaseCommand

from dds.accounts.models import AdvUser, MasterUser
from dds.networks.models import Network
from dds.store.models import UsdRate
from django_celery_beat.models import (
    IntervalSchedule,
    CrontabSchedule,
    SolarSchedule,
    ClockedSchedule,
    PeriodicTask,
)

from dds.settings import config


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
        for rate in config.USD_RATES:
            obj, created = UsdRate.objects.get_or_create(
                coin_node=rate.coin_node,
                symbol=rate.symbol,
                name=rate.name,
                image=rate.image,
                address=rate.address,
                network=rate.network,
                fee_discount=rate.fee_discount
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
