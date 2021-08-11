from dds.rates.models import UsdRate
from dds.consts import SUPPORTED_CURRENCIES
from dds.consts import DECIMALS


def get_usd_prices():
    return {rate.symbol: rate.rate for rate in UsdRate.objects.all()}


def calculate_amount(original_amount, from_currency, to_currency='USD'):
    '''
    print('Calculating amount, original: {orig}, from {from_curr} to {to_curr}'.format(
        orig=original_amount,
        from_curr=from_currency,
        to_curr=to_currency),
        flush=True)
    '''
    usd_rates = get_usd_prices()
    if to_currency == 'USD':
        usd_rates[to_currency] = 1
    currency_rate = usd_rates[from_currency] / usd_rates[to_currency]
    amount = int(float(original_amount) / DECIMALS[from_currency] * DECIMALS[to_currency] * float(currency_rate))
    return amount, currency_rate
