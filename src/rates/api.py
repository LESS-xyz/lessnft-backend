from src.rates.models import UsdRate


def get_usd_prices():
    return {rate.symbol: rate.rate for rate in UsdRate.objects.all()}


def get_decimals(currency):
    if currency == "USD":
        return 10 ** 2
    return UsdRate.objects.filter(symbol=currency).first().get_decimals


def calculate_amount(original_amount, from_currency, to_currency='USD'):
    '''
    original amount with decimals
    '''
    usd_rates = get_usd_prices()
    if to_currency == 'USD':
        usd_rates[to_currency] = 1
    currency_rate = usd_rates[from_currency] / usd_rates[to_currency]
    amount = float(original_amount) / get_decimals(from_currency) * float(currency_rate)
    return float("{0:.2f}".format(amount)), currency_rate
