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
    return {
        "rate": response["market_data"]["current_price"][QUERY_FSYM],
        "coin_node": response.get("id"),
        "symbol": response.get("symbol"),
        "name": response.get("name"),
        "image": response.get("image", {}).get("small"),
        "address": response.get("contract_address"),
    }


if __name__ == "__main__":
    while True:
        coin_nodes = UsdRate.objects.all().values_list('coin_node', flat=True)
        for coin_node in coin_nodes:
            try:
                rate = get_rate(coin_node)
            except Exception as e:
                print("\n".join(traceback.format_exception(*sys.exc_info())), flush=True)
                time.sleep(RATES_CHECKER_TIMEOUT)
                continue
            rates = UsdRate.objects.filter(symbol=rate["symbol"])
            rates.update(
                coin_node=rate["coin_node"],
                name=rate["name"],
                image=rate["image"],
                address=rate["address"],
                rate=rate["rate"],
            )
            if not all(rate.decimal for rate in rates):
                for rate in rates:
                    rate.set_decimals()
        time.sleep(RATES_CHECKER_TIMEOUT)
