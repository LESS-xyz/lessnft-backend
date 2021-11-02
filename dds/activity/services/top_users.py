import json
from django.utils import timezone
from datetime import timedelta
from django.db.models import Sum, F, Count
from dds.accounts.models import AdvUser
from dds.activity.models import TokenHistory, UserStat, UserAction
from dds.rates.api import calculate_amount
from dds.utilities import get_periods


def update_users_stat(network):
    types = {
        'new_owner': 'buyer',
        'old_owner': 'seller',
    }
    periods = get_periods('day', 'week', 'month')
    for type_ in types.keys():
        user_filter = {f"{type_}__method": "Buy"}
        users = AdvUser.objects.filter(**user_filter).distinct()
        for user in users:
            user_stat, _ = UserStat.objects.get_or_create(network, user=user)

            stat = getattr(user_stat, types[type_])
            if isinstance(stat, str):
                stat = json.loads(stat)
            else:
                stat = dict()

            for period, time_delta in periods.items():
                filter_data = {
                    "token__currency__network": network,
                    "date__gte": time_delta,
                    "method": "Buy",
                    type_: user,
                }
                history = TokenHistory.objects.filter(**filter_data).annotate(
                    old_owner=F(type_),
                    price_=F('USD_price'),
                ).values('user').annotate(price=Sum('price_'))
                if history:
                    stat[period] = history[0].get('price')
            setattr(user_stat, types[type_], json.dumps(stat, default=float))

            user_stat.save()
 
    for period, time_delta in periods.items():
        users = AdvUser.objects.filter(following__date__gte=time_delta).annotate(follow_count = Count('following'))
        for user in users:
            user_stat = UserStat.objects.filter(user=user)
            if not user_stat.exists():
                user_stat = UserStat.objects.bulk_create([
                    UserStat(network=network, user=user) for network in networks
                ])
            stat = getattr(user_stat[0], 'follows')
            if isinstance(stat, str):
                stat = json.loads(stat)
            else:
                stat = dict()
            stat[period] = user.follow_count

            setattr(user_stat, types[type_], json.dumps(stat, default=float))
            user_stat.save()


def get_top_users(type_, period, network):
    stat_data = f"{type_}__{period}"
    user_filter = {"network": network, f"{type_}__isnull": False}
    users = UserStat.objects.filter(**user_filter)
    users = [u for u in users if isinstance(getattr(u, type_), str) and json.loads(getattr(u, type_))[period]]
    users = sorted(users, key=lambda x: json.loads(getattr(x, type_))[period])
    return users
