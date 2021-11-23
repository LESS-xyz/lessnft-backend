from datetime import timedelta
from dateutil.relativedelta import relativedelta

from typing import Optional

from django.db.models import Avg
from django.db.models.functions import TruncMonth, TruncDay, TruncHour

from src.activity.models import TokenHistory
from src.utilities import get_periods


class PriceHistory:
    def __init__(self, _token, _period):
        self.token = _token
        self.period = _period
        self.trunc_func = None
        self.range_delta = None
        self.delta = None
        self.range = None
        self.filter_period = None
        self.periods = get_periods('day', 'week', 'month', 'year')

        self.init_params()

        self.filter_period = self.periods[self.period]

    def _history_day(self) -> None:
        self.delta = timedelta(hours=1)
        self.range_delta = 'hours'
        self.trunc_func = TruncHour
        self.range = 24 

    def _history_week(self) -> None:
        self.delta = timedelta(days=1) 
        self.range_delta = 'days'
        self.trunc_func = TruncDay
        self.range = 7 

    def _history_month(self) -> None:
        self.delta = timedelta(days=1) 
        self.range_delta = 'days'
        self.trunc_func = TruncDay
        self.range = 30 

    def _history_year(self) -> None:
        self.delta = timedelta(days=30)
        self.range_delta = 'months'
        self.trunc_func = TruncMonth
        self.range = 12 

    def init_params(self) -> None:
        getattr(self, f"_history_{self.period}")()

    def get_last_value(self, listing_history) -> Optional[float]:
        """ 
        if listing is empty or date of first listing 
        does't coincide with start date of period, 
        then we get the last value before this period.
        """
        if not listing_history.keys() or (list(listing_history.keys())[0] != self.filter_period + timedelta(days=1)):
            listing = TokenHistory.objects.filter(
                token=self.token,
                method="Listing",
            ).filter(date__lte=self.filter_period).annotate(
                period=self.trunc_func('date')
            ).values('period').annotate(avg_price=Avg('price')).values('period', 'avg_price')
            if listing:
                return listing[len(listing)-1].get('avg_price')
        return None
 
    @property
    def date_list(self) -> list:
        """ Return list of periods """
        date_list = [
            self.filter_period + self.delta + relativedelta(**{self.range_delta: days_count})
            for days_count in range(self.range)
        ]
        if self.period == 'year':
            date_list = [d.replace(day=1) for d in date_list]
        return date_list

    @property
    def date_replace(self) -> dict:
        date_replace = {
            'minute': 0,
            'second': 0,
            'microsecond': 0,
        }
        if self.period != 'day':
            date_replace['hour'] = 0
        return date_replace

    def get_history(self) -> list:
        listing_history = TokenHistory.objects.filter(
            token=self.token, 
            method="Listing",
        ).filter(date__gte=self.filter_period).annotate(
            period=self.trunc_func('date')
        ).values('period').annotate(avg_price=Avg('price')).values('period', 'avg_price')
        listing_history = {h.get('period'): h.get('avg_price') for h in listing_history}

        last_value = self.get_last_value(listing_history)

        response = list()
        for date in self.date_list:
            date = date.replace(**self.date_replace)
            avg_price = listing_history.get(date)
            if avg_price is None:
                avg_price = last_value
            else:
                last_value = avg_price
            response.append({'date': date, 'avg_price': avg_price})
        return response
