import os
import sys
import time
import requests
import traceback

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "dds.settings")
import django

django.setup()

from dds.rates.models import UsdRate
from dds.settings import RATES_CHECKER_TIMEOUT


API_URL = "https://api.coingecko.com/api/v3/coins/{coin_code}"


QUERY_FSYM = "usd"


def get_rate(coin_code):
    res = requests.get(API_URL.format(coin_code=coin_code))
    if res.status_code != 200:
        raise Exception("cannot get exchange rate for {}".format(QUERY_FSYM))
    response = res.json()
    return response["symbol"], response["market_data"]["current_price"][QUERY_FSYM]


if __name__ == "__main__":
    while True:
        coin_nodes = UsdRate.objects.all().values_list('coin_node', flat=True)
        for coin_node in coin_nodes:
            try:
                symbol, rate = get_rate(coin_node)
            except Exception as e:
                print("\n".join(traceback.format_exception(*sys.exc_info())), flush=True)
                time.sleep(RATES_CHECKER_TIMEOUT)
                continue
            rates = UsdRate.objects.filter(coin_node=coin_node)
            rates.update(rate=rate)
        time.sleep(RATES_CHECKER_TIMEOUT)
