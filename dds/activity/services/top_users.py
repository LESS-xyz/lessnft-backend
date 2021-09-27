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


def update_users_stat():
    for type_ in ["new_owner", "old_owner"]:
        user_filter = {f"{type_}__method": "Buy"}
        users = AdvUser.objects.filter(**user_filter).distinct()
        for user in users:
            user_stat, _ = UserStat.objects.get_or_create(user=user)

            for period, time_delta in PERIODS.items():
                filter_data = {
                    "date__gte": time_delta, 
                    "method": "Buy", 
                    type_: user,
                }
                history = TokenHistory.objects.filter(**filter_data).annotate(
                    user=F(type_), 
                    price=F('USD_price'),
                ).values('user').annotate(price=Sum('price'))
                getattr(user_stat, type_)[period] = history.get('price')

            user_stat.save()


def get_top_users(type_, period):
    stat_data = f"{type_}__{period}"
    user_filter = {f"{stat_data}__isnull": False}
    return UserStat.objects.filter(**user_filter).order_by(f"-{stat_data}")[:15]
