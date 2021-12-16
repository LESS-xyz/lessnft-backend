from datetime import date, timedelta

import pytest

from src.utilities import RedisClient
from src.store.models import Status
from src.activity.services.top_collections import (
    update_collection_stat,
    get_top_collections,
)
from src.activity.models import CollectionStat


@pytest.mark.django_db
def test_collection_redis_save(mixer):
    yesterday = date.today() - timedelta(days=1)
    redis = RedisClient()
    collection = mixer.blend(
        "store.Collection",
        status=Status.COMMITTED,
        network__name="Ethereum",
    )
    history = mixer.blend(
        "activity.TokenHistory",
        token__collection=collection,
        method="Buy",
        USD_price=100,
    )
    history.date = yesterday
    history.save()

    redis.connection.flushall()
    update_collection_stat()
    get_top_collections("Ethereum", "week")

    key = f"top_collection__week__{date.today().strftime('%Y-%m-%d')}__Ethereum"
    assert redis.connection.get(key) is not None


@pytest.mark.django_db
def test_update_collection_stat(mixer):
    yesterday = date.today() - timedelta(days=1)
    collection_1 = mixer.blend("store.Collection", status=Status.COMMITTED)
    collection_2 = mixer.blend("store.Collection", status=Status.COMMITTED)

    hisorys = mixer.cycle(3).blend(
        "activity.TokenHistory",
        token__collection=collection_1,
        method="Buy",
        USD_price=100,
    )
    for i, hisory in enumerate(hisorys):
        hisory.date = date.today() - timedelta(days=i)
        hisory.save()

    history_2 = mixer.blend(
        "activity.TokenHistory",
        token__collection=collection_2,
        method="Buy",
        USD_price=55,
    )
    history_2.date = yesterday
    history_2.save()

    update_collection_stat()

    assert CollectionStat.objects.count() == 2
    assert all([c.date == yesterday for c in CollectionStat.objects.all()])

    assert CollectionStat.objects.get(collection=collection_1).amount == 100
    assert CollectionStat.objects.get(collection=collection_2).amount == 55


@pytest.mark.django_db
def test_top_collections(api, mixer):
    collection = mixer.blend("store.Collection", status=Status.COMMITTED)
    mixer.blend(
        "activity.CollectionStat",
        date=date.today(),
        amount=50,
        collection=collection,
    )
    mixer.blend(
        "activity.CollectionStat",
        date=date.today() - timedelta(days=1),
        amount=100,
        collection=collection,
    )

    # day
    response = api.get(
        "/api/v1/activity/top-collections/",
        {
            "sort_period": "day",
            "network": collection.network.name,
        },
    )
    assert response.status_code == 200
    response_data = response.json().get("results")[0]
    assert response_data.get("price") == 50.0
    assert response_data.get("difference") == "-50.00%"

    # week
    response = api.get(
        "/api/v1/activity/top-collections/",
        {
            "sort_period": "week",
            "network": collection.network.name,
        },
    )
    assert response.status_code == 200
    response_data = response.json().get("results")[0]
    assert response_data.get("price") == 150.0
    assert response_data.get("difference") == None


@pytest.mark.django_db
def test_top_collections_total_owners(api, mixer):
    collection = mixer.blend(
        "store.Collection",
        status=Status.COMMITTED,
        standart="ERC721",
    )
    mixer.blend(
        "activity.CollectionStat",
        date=date.today(),
        amount=50,
        collection=collection,
    )
    mixer.blend(
        "activity.CollectionStat",
        date=date.today() - timedelta(days=1),
        amount=100,
        collection=collection,
    )
    users = mixer.cycle(3).blend("accounts.AdvUser")
    mixer.cycle(3).blend(
        "store.Token",
        status=Status.COMMITTED,
        owner=(u for u in users),
        collection=collection,
    )
    mixer.blend(
        "store.Token",
        owner=users[0],
        status=Status.COMMITTED,
        collection=collection,
    )

    response = api.get(
        "/api/v1/activity/top-collections/",
        {
            "sort_period": "day",
            "network": collection.network.name,
        },
    )

    assert response.status_code == 200
    response_data = response.json().get("results")[0]
    assert response_data.get("total_items") == 4
    assert response_data.get("total_owners") == 3
