import json
from django.db.models import Sum, F, Exists, OuterRef, Count
from src.store.models import Collection, Token
from src.store.serializers import CollectionSlimSerializer
from src.activity.models import TokenHistory, CollectionStat
from datetime import date, timedelta
from src.utilities import get_periods
from src.utilities import RedisClient
from src.settings import config


def update_collection_stat():
    filter_day = date.today() - timedelta(days=1)
    token_history = TokenHistory.objects.filter(
        date__year=filter_day.year,
        date__month=filter_day.month,
        date__day=filter_day.day,
        method="Buy",
    )
    result = (
        token_history.annotate(
            price_=F("USD_price"),
            collection=F("token__collection"),
        )
        .values("collection")
        .annotate(price=Sum("price_"))
    )
    for data in result:
        collection = Collection.objects.filter(id=data.get("collection")).first()
        if not collection:
            continue
        collection, _ = CollectionStat.objects.get_or_create(
            collection=collection,
            date=filter_day,
        )
        collection.amount = data.get("price")
        collection.save()


def _get_collections_stat(collections_id, start, end):
    end += timedelta(days=1)
    return (
        CollectionStat.objects.filter(
            collection_id__in=collections_id,
            date__lte=start,
            date__gte=end,
        )
        .values("collection")
        .annotate(price=Sum("amount"))
    )


def get_diff(value1, value2) -> str:
    if not value2:
        return None
    diff = (value2 - value1) * 100 / value2
    if diff < 0:
        diff = abs(diff)
        return f"+{round(diff, 2)}%"
    return f"-{round(diff, 2)}%"


def get_top_collections(network, period, tag=None):
    periods = get_periods("day", "week", "month")
    main_start = date.today()
    main_end = periods[period]
    prev_end = get_periods("day", "week", "month", from_date=main_end)
    prev_end = prev_end[period]

    redis = RedisClient()
    redis_key = f"top_collection__{period}__{main_start}__{network}"

    data = redis.connection.get(redis_key)

    if data:
        return json.loads(data)

    collections = Collection.objects.committed().network(network)
    if tag is not None:
        collections = collections.filter(
            Exists(
                Token.objects.committed().filter(tag=tag, collection__id=OuterRef("id"))
            )
        )
    collections = collections.values_list("id", flat=True)
    main_collections = list(_get_collections_stat(collections, main_start, main_end))

    if not main_collections:
        return []

    main_collections.sort(key=lambda val: val.get("price", 0), reverse=True)
    main_collections = list(main_collections)

    main_collections_id = [col.get("collection") for col in main_collections]
    prev_collections = _get_collections_stat(main_collections_id, main_end, prev_end)
    prev_collections = {
        col.get("collection"): col.get("price") for col in prev_collections
    }

    for collection in main_collections:
        collection["difference"] = get_diff(
            collection.get("price"), prev_collections.get(collection["collection"])
        )
        collection_object = Collection.objects.get(id=collection["collection"])
        collection["collection"] = CollectionSlimSerializer(collection_object).data
        tokens = collection_object.token_set.filter(
            selling=True,
            currency_price__isnull=False,
        )
        token_prices = [token.usd_price for token in tokens]
        collection["floor_price"] = min(token_prices) if token_prices else None
        collection["total_items"] = collection_object.token_set.count()

        owner_value = "owner" if collection_object.standart == "ERC721" else "owners"
        collection["total_owners"] = (
            collection_object.token_set.all()
            .values(owner_value)
            .distinct()
            .aggregate(Count(owner_value))
            .get("owner__count")
        )

    redis.connection.set(
        redis_key,
        json.dumps(main_collections, ensure_ascii=False, default=str),
        ex=config.REDIS_EXPIRATION_TIME,
    )

    return main_collections
