from celery import shared_task
from dds.activity.services.top_users import update_users_stat


@shared_task(name="update_top_users_info")
def update_top_users_info():
    print(f"Start update top users info")
    update_users_stat()
