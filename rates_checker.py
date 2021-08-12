import os
import sys
import time
import requests
import traceback
from dds.settings import ERC20_ADDRESS

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dds.settings')
import django

django.setup()

from dds.rates.models import UsdRate
from dds.settings import RATES_CHECKER_TIMEOUT


API_URL = 'https://api.coingecko.com/api/v3/coins/{coin_code}'


QUERY_FSYM = 'usd'


def get_rate(tsym):
    res = requests.get(API_URL.format(coin_code=tsym))
    if res.status_code != 200:
        raise Exception('cannot get exchange rate for {}'.format(QUERY_FSYM))
    response = res.json()
    return {
        "rate": response['market_data']['current_price'][QUERY_FSYM],
        "coin_node": response.get("id"),
        "symbol": response.get("symbol"),
        "name": response.get("name"),
        "image": response.get("image", {}).get("small"),
        "address": response.get("contract_address"),
    }


if __name__ == '__main__':
    while True:
        usd_rates = []

        try:
            for rate in UsdRate.objects.all():
                usd_rates.append(get_rate(rate.coin_node))
        except Exception as e:
            print('\n'.join(traceback.format_exception(*sys.exc_info())), flush=True)
            time.sleep(RATES_CHECKER_TIMEOUT)
            continue
        for rate in usd_rates:
            try:
                rate_object = UsdRate.objects.get(symbol=rate["symbol"])
            except UsdRate.DoesNotExist:
                rate_object = UsdRate(symbol=rate["symbol"])
                rate_object.coin_node = rate["coin_node"]
                rate_object.name = rate["name"]
                rate_object.image = rate["image"]
                rate_object.address = rate["address"]
            rate_object.rate = rate["rate"]
            rate_object.save()
            if not rate_object.decimal:
                rate_object.set_decimals()
        time.sleep(RATES_CHECKER_TIMEOUT)
