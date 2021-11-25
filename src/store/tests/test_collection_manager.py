from datetime import date, timedelta

import pytest

from src.store.models import Status, Collection


@pytest.mark.django_db
def test_collection_manager(api, mixer):
    network = mixer.blend(
        'networks.Network',
        name = 'Ethereum',
    )
    networks_polygon = mixer.cycle(3).blend(
        'networks.Network',
        name = 'Polygon',
    )
    user = mixer.blend('accounts.AdvUser', display_name='testuser')

    collections = mixer.cycle(5).blend(
        "store.Collection",
        status=Status.COMMITTED,
        network=network,
        creator=user
    )

    collection = mixer.blend(
        "store.Collection",
        name = 'test_collection',
        status = Status.COMMITTED,
        short_url = 'testurl'
    )
    tokens = mixer.cycle(5).blend('store.Token', collection=collection)
    expired_collection = mixer.blend(
        "store.Collection",
        name = 'expired_collection',
        status = Status.EXPIRED,
    )

    assert len(Collection.objects.commited()) == 6
    assert len(Collection.objects.user_collections(user=user, network=network)) == 5
    assert Collection.objects.get_by_short_url('testurl').name == 'test_collection'
    assert len(Collection.objects.hot_collections()) == 1
    assert len(Collection.objects.network('Polygon')) == 3
