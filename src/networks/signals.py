from django.db.models.signals import post_save
from django.dispatch import receiver

from src.accounts.models import MasterUser
from src.networks.models import Network
from src.settings import config


@receiver(post_save, sender=Network)
def network_post_save_dispatcher(sender, instance, created, *args, **kwargs):
    create_master_user(instance, created)


def create_master_user(network, created):
    """
    Create MasterUser objects for new Network.
    """
    if created:
        MasterUser.objects.create(
            network=network,
            commission=config.DEFAULT_COMMISSION,
        )
