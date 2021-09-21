from itertools import groupby
from datetime import datetime, timedelta
from django.db.models import Sum, F
from dds.accounts.models import AdvUser
from dds.activity.models import TokenHistory, UserStat
from dds.rates.api import calculate_amount


def update_users_stat():
    periods = {
        'day': datetime.today() - timedelta(days=1),
        'week': datetime.today() - timedelta(days=7),
        'month': datetime.today() - timedelta(days=30),
    }
    for period_name, time_delta in periods.values():
        period = f'period_{period_name}'
        buyer_history = TokenHistory.objects.filter(date__gte=time_delta, method="Buy").annotate(
            user=F('new_owner'), 
            currency=F('token__currency__symbol'),
        ).values('user', 'currency').annotate(price=Sum('price'))
        buyer_history = [{'user': h.get("user"), period: calculate_amount(h.get("price"), h.get("currency"))[1]} for h in buyer_history]
        buyer_history.sort(key=lambda item: item['user'])
        sorted_history = list()
        for key, value in groupby(buyer_history,key=lambda item: item['user']):
            sorted_history.append({'user': key, 'price':sum(v[period] for v in value)})

        for item in sorted_history:
            user_stat = UserStat.objects.get_or_create(user_id=item.get('user'))
            setattr(user_stat, period, item.get('price'))
            user_stat.save()


def get_top_users(type_, period):
    ...
