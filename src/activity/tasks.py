from celery import shared_task
from src.activity.services.top_users import update_users_stat
from src.networks.models import Network


@shared_task(name="update_top_users_info")
def update_top_users_info():
    print(f"Start update top users info")
    networks = Network.objects.all()
    for network in networks:
        update_users_stat(network)
