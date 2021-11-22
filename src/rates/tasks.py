import sys
import requests
import traceback

from src.settings import config

from src.rates.models import UsdRate

from celery import shared_task
from src.settings import config


QUERY_FSYM = "usd"


def get_rate(coin_code):
    res = requests.get(config.API_URL.format(coin_code=coin_code))
    if res.status_code != 200:
        raise Exception("cannot get exchange rate for {}".format(QUERY_FSYM))
    response = res.json()
    return response["market_data"]["current_price"][QUERY_FSYM]


@shared_task(name="rates_checker")
def rates_checker():
    coin_nodes = UsdRate.objects.all().values_list('coin_node', flat=True)
    for coin_node in coin_nodes:
        try:
            rate = get_rate(coin_node)
        except Exception as e:
            print("\n".join(traceback.format_exception(*sys.exc_info())), flush=True)
            continue
        rates = UsdRate.objects.filter(coin_node=coin_node)
        rates.update(rate=rate)
