from datetime import date, timedelta

import pytest

from src.store.models import Status


@pytest.mark.django_db
def test_top_collections(api, mixer):
    collection = mixer.blend("store.Collection", status=Status.COMMITTED)
    mixer.blend(
        "activity.CollectionStat", date=date.today(), amount=50, collection=collection
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
    assert response.json()[0].get("price") == 50.0
    assert response.json()[0].get("difference") == "-50.00%"

    # week
    response = api.get(
        "/api/v1/activity/top-collections/",
        {
            "sort_period": "week",
            "network": collection.network.name,
        },
    )
    assert response.status_code == 200
    assert response.json()[0].get("price") == 150.0
    assert response.json()[0].get("difference") == None
