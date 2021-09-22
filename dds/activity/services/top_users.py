from itertools import groupby
from django.utils import timezone
from datetime import timedelta
from django.db.models import Sum, F
from dds.accounts.models import AdvUser
from dds.activity.models import TokenHistory, UserStat
from dds.rates.api import calculate_amount


# TODO: mb get from config
PERIODS = {
    'day': timezone.now() - timedelta(days=1),
    'week': timezone.now() - timedelta(days=7),
    'month': timezone.now() - timedelta(days=30),
}


def _update_users_stat(users, type_):
    for user in users:
        user_stat, _ = UserStat.objects.get_or_create(user=user)

        for period, time_delta in PERIODS.items():
            filter_data = {
                "date__gte": time_delta, 
                "method": "Buy", 
                type_: user,
            }
            buyer_history = TokenHistory.objects.filter(**filter_data).annotate(
                user=F('new_owner'), 
                price=F('usd_price'),
            ).values('user').annotate(price=Sum('price'))
            user_stat.buyer[period] = history.get('price')

        user_stat.save()


def update_users_stat():
    buyers = AdvUser.objects.filter(new_owner__method="Buy").distinct()
    sellers = AdvUser.objects.filter(old_owner__method="Buy").distinct()
    _update_users_stat(buyers, 'new_owner')
    _update_users_stat(sellers, 'old_owner')


def get_top_users(type_, period):
    ...
