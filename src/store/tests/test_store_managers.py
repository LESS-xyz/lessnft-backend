import pytest
from src.store.models import Status, Collection, Token, Bid
from django.core.exceptions import ObjectDoesNotExist
from django.contrib.auth.models import AnonymousUser


@pytest.mark.django_db
def test_check_committed(mixer):
    mixer.blend(
        "store.Collection",
        status=Status.PENDING,
        network__name="Ethereum",
    )
    mixer.cycle(2).blend(
        "store.Collection", status=Status.COMMITTED, network__name="Ethereum"
    )
    mixer.cycle(3).blend(
        "store.Collection", status=Status.COMMITTED, network__name="Polygon"
    )

    assert len(Collection.objects.committed()) == 5
    assert all([c.status == Status.COMMITTED for c in Collection.objects.committed()])


@pytest.mark.django_db
def test_check_user_collections(mixer):
    user = mixer.blend("accounts.AdvUser")
    second_user = mixer.blend("accounts.AdvUser")

    network_eth = mixer.blend(
        "networks.Network",
        name="Ethereum",
    )
    network_polygon = mixer.blend(
        "networks.Network",
        name="Polygon",
    )

    mixer.cycle(2).blend(
        "store.Collection", status=Status.PENDING, network=network_eth, creator=user
    )
    mixer.cycle(5).blend(
        "store.Collection", status=Status.COMMITTED, network=network_eth, creator=user
    )
    mixer.cycle(2).blend("store.Collection", status=Status.COMMITTED, is_default=True)
    mixer.blend(
        "store.Collection",
        status=Status.COMMITTED,
        network=network_polygon,
        creator=second_user,
    )
    anonim = AnonymousUser()

    """Check user collections"""
    assert len(Collection.objects.user_collections(user=user, network=network_eth)) == 5
    assert len(Collection.objects.user_collections(user=user)) == 7
    assert len(Collection.objects.user_collections(user=second_user)) == 3
    assert (
        len(
            Collection.objects.user_collections(
                user=second_user, network=network_polygon
            )
        )
        == 1
    )
    assert not Collection.objects.user_collections(user=None, network=network_polygon)
    try:
        Collection.objects.user_collections(user=anonim)
        assert False
    except AssertionError:
        assert True


@pytest.mark.django_db
def test_collections_by_short_url(mixer):
    polygon_collection = mixer.blend(
        "store.Collection",
        name="test_collection",
        status=Status.COMMITTED,
        short_url="testurl",
        network__name="Polygon",
    )
    eth_collection = mixer.blend(
        "store.Collection",
        name="test_collection_2",
        status=Status.COMMITTED,
        short_url="testurl2",
        network__name="Ethereum",
    )

    """Checking getting collection by short_url and id"""
    assert Collection.objects.get_by_short_url("testurl").name == "test_collection"
    assert Collection.objects.get_by_short_url("testurl2").name == "test_collection_2"
    try:
        Collection.objects.get_by_short_url("testurl3")
        assert False
    except ObjectDoesNotExist:
        assert True

    assert (
        Collection.objects.get_by_short_url(polygon_collection.id).name
        == "test_collection"
    )
    assert (
        Collection.objects.get_by_short_url(str(eth_collection.id)).name
        == "test_collection_2"
    )


@pytest.mark.django_db
def test_check_collections_by_network(mixer):
    mixer.blend("store.Collection", status=Status.PENDING, network__name="Ethereum")
    mixer.cycle(5).blend(
        "store.Collection", status=Status.COMMITTED, network__name="Ethereum"
    )
    mixer.cycle(3).blend("store.Collection", status=Status.COMMITTED, is_default=True)
    mixer.blend("store.Collection", status=Status.COMMITTED, network__name="Polygon")

    """Checking Collections by network"""
    assert len(Collection.objects.network("Polygon")) == 1
    assert len(Collection.objects.network("Ethereum")) == 6
    assert len(Collection.objects.network(None)) == 10
    assert len(Collection.objects.network("undefined")) == 10
    assert not Collection.objects.network("Fake").exists()
    assert not Collection.objects.network(["Ethereum"]).exists()


@pytest.mark.django_db
def test_check_hot_collections(mixer):
    collection = mixer.blend(
        "store.Collection",
        name="main_collection",
        status=Status.COMMITTED,
        network__name="Ethereum",
    )
    default_collection = mixer.blend(
        "store.Collection", status=Status.COMMITTED, is_default=True
    )
    mixer.blend("store.Collection", status=Status.COMMITTED, network__name="Ethereum")
    pending_tokens_collection = mixer.blend(
        "store.Collection",
        name="pending_collection",
        status=Status.COMMITTED,
        network__name="Ethereum",
    )

    mixer.cycle(5).blend("store.Token", collection=collection, status=Status.PENDING)
    mixer.cycle(3).blend("store.Token", collection=collection, status=Status.COMMITTED)
    mixer.cycle(3).blend(
        "store.Token", collection=default_collection, status=Status.COMMITTED
    )
    mixer.cycle(3).blend(
        "store.Token", collection=pending_tokens_collection, status=Status.PENDING
    )

    """Checking Hot Collections (non-default collections with committed tokens)"""
    assert len(Collection.objects.hot_collections()) == 1
    assert Collection.objects.hot_collections().first().name == "main_collection"
    assert all(
        [c.status == Status.COMMITTED for c in Collection.objects.hot_collections()]
    )


@pytest.mark.django_db
def test_token_manager(mixer):
    collection_eth = mixer.blend(
        "store.Collection",
        name="test_collection",
        status=Status.COMMITTED,
        network__name="Ethereum",
    )
    collection_polygon = mixer.blend(
        "store.Collection",
        name="test_collection",
        status=Status.COMMITTED,
        network__name="Polygon",
    )

    mixer.cycle(3).blend(
        "store.Token", collection=collection_eth, status=Status.COMMITTED
    )
    mixer.cycle(2).blend(
        "store.Token", collection=collection_polygon, status=Status.COMMITTED
    )
    mixer.cycle(2).blend(
        "store.Token", collection=collection_polygon, status=Status.PENDING
    )

    """Checking the ammount of commited Tokens"""
    assert len(Token.objects.committed()) == 5
    assert all([t.status == Status.COMMITTED for t in Token.objects.committed()])

    """Checking Tokens by network"""
    assert len(Token.objects.network("Polygon")) == 4
    assert len(Token.objects.network("Ethereum")) == 3
    assert len(Token.objects.network(None)) == 7
    assert not Token.objects.network("Fake")
    assert not Token.objects.network(["Polygon"])


@pytest.mark.django_db
def test_bid_committed(mixer):
    mixer.cycle(2).blend("store.Bid", state=Status.EXPIRED)
    mixer.cycle(3).blend("store.Bid", state=Status.COMMITTED)

    assert len(Bid.objects.committed()) == 3
    assert all([bid.state == Status.COMMITTED for bid in Bid.objects.committed()])
