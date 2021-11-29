import pytest
from src.store.models import Status, Collection, Token
from django.core.exceptions import ObjectDoesNotExist


@pytest.mark.django_db
def test_check_commited(mixer):
    mixer.blend(
        "store.Collection",
        name='expired_collection',
        status=Status.EXPIRED,
        network__name='Ethereum',
    )
    mixer.cycle(5).blend(
        "store.Collection",
        status=Status.COMMITTED,
        network__name='Ethereum'
    )
    mixer.cycle(7).blend(
        "store.Collection",
        status=Status.COMMITTED,
        is_default=True
    )
    mixer.blend(
        "store.Collection",
        status=Status.COMMITTED,
        network__name='Polygon'
    )

    '''Checking "committed" collections querry set'''
    assert len(Collection.objects.committed()) == 13
    assert all([c.status==Status.COMMITTED for c in Collection.objects.committed()])


@pytest.mark.django_db
def test_check_user_collections(mixer):
    user = mixer.blend('accounts.AdvUser', display_name='testuser')
    second_user = mixer.blend('accounts.AdvUser', display_name='testuser2')

    network_eth = mixer.blend(
        'networks.Network',
        name = 'Ethereum',
    )
    network_polygon= mixer.blend(
        'networks.Network',
        name = 'Polygon',
    )

    mixer.cycle(5).blend(
        "store.Collection",
        status=Status.COMMITTED,
        network=network_eth,
        creator=user
    )
    mixer.cycle(3).blend(
        "store.Collection",
        status=Status.COMMITTED,
        creator=user,
        is_default=True
    )
    mixer.cycle(7).blend(
        "store.Collection",
        status=Status.COMMITTED,
        creator=second_user,
        is_default=True
    )
    mixer.blend(
        "store.Collection",
        status=Status.COMMITTED,
        network=network_polygon,
        creator=second_user
    )

    '''Check user collections'''
    assert len(Collection.objects.user_collections(user=user, network=network_eth)) == 5
    assert len(Collection.objects.user_collections(user=user)) == 15
    assert len(Collection.objects.user_collections(user=second_user)) == 11
    assert len(Collection.objects.user_collections(user=second_user, network=network_polygon)) == 1
    assert not Collection.objects.user_collections(user=None, network=network_polygon)


@pytest.mark.django_db
def test_collections_by_short_url(mixer):
    polygon_collection = mixer.blend(
        "store.Collection",
        name = 'test_collection',
        status = Status.COMMITTED,
        short_url = 'testurl',
        network__name='Polygon'
    )
    eth_collection = mixer.blend(
        "store.Collection",
        name = 'test_collection_2',
        status = Status.COMMITTED,
        short_url = 'testurl2',
        network__name='Ethereum'
    )

    '''Checking getting collection by short_url and id'''
    assert Collection.objects.get_by_short_url('testurl').name == 'test_collection'
    assert not Collection.objects.get_by_short_url('testurl').name == 'test_collection_2'
    assert Collection.objects.get_by_short_url('testurl2').name == 'test_collection_2'
    try:
        Collection.objects.get_by_short_url('testurl3')
    except ObjectDoesNotExist:
        assert True


    assert Collection.objects.get_by_short_url(polygon_collection.id).name == 'test_collection'
    assert Collection.objects.get_by_short_url(str(eth_collection.id)).name == 'test_collection_2'



@pytest.mark.django_db
def test_check_collections_by_network(mixer):
    mixer.blend(
        "store.Collection",
        name='expired_collection',
        status=Status.EXPIRED,
        network__name='Ethereum'
    )
    mixer.cycle(5).blend(
        "store.Collection",
        status=Status.COMMITTED,
        network__name='Ethereum'
    )
    mixer.cycle(3).blend(
        "store.Collection",
        status=Status.COMMITTED,
        is_default=True
    )
    mixer.blend(
        "store.Collection",
        status=Status.COMMITTED,
        network__name='Polygon'
    )

    '''Checking Collections by network'''
    assert len(Collection.objects.network('Polygon')) == 1
    assert len(Collection.objects.network('Ethereum')) == 6
    assert len(Collection.objects.network(None)) == 10
    assert not Collection.objects.network('Fake').exists()
    assert not Collection.objects.network(['Ethereum']).exists()


@pytest.mark.django_db
def test_check_hot_collections(mixer):
    collection = mixer.blend(
        "store.Collection",
        name='expired_collection',
        status=Status.COMMITTED,
        network__name='Ethereum'
    )
    default_collection = mixer.blend(
        "store.Collection",
        status=Status.COMMITTED,
        is_default=True
    )
    pending_collection = mixer.blend(
        "store.Collection",
        status=Status.PENDING,
        network__name='Ethereum'
    )
    mixer.blend(
        "store.Collection",
        status=Status.COMMITTED,
        network__name='Ethereum'
    )

    mixer.cycle(5).blend(
        'store.Token', 
        collection=collection, 
        status=Status.PENDING
    )
    mixer.cycle(3).blend('store.Token', collection=collection, status=Status.COMMITTED)
    mixer.cycle(3).blend('store.Token', collection=default_collection, status=Status.COMMITTED)
    mixer.cycle(3).blend('store.Token', collection=pending_collection, status=Status.COMMITTED)

    '''Checking Hot Collections (non-default collections with committed tokens)'''
    assert len(Collection.objects.hot_collections()) == 2
    assert not Collection.objects.hot_collections() == 0
    assert all([c.status==Status.COMMITTED or c.status==Status.PENDING for c in Collection.objects.hot_collections()])


@pytest.mark.django_db
def test_token_manager(mixer):
    collection_eth = mixer.blend(
        "store.Collection",
        name = 'test_collection',
        status = Status.COMMITTED,
        network__name='Ethereum' 
    )
    collection_polygon = mixer.blend(
        "store.Collection",
        name = 'test_collection',
        status = Status.COMMITTED,
        network__name='Polygon' 
    )
    mixer.cycle(3).blend(
        'store.Token',
        collection=collection_eth,
        status=Status.COMMITTED
    )
    mixer.cycle(2).blend(
        'store.Token',
        collection=collection_polygon,
        status=Status.COMMITTED
    )
    mixer.cycle(2).blend(
        'store.Token', 
        collection=collection_polygon,
        status=Status.EXPIRED
    )


    '''Checking the ammount of commited Tokens'''
    assert len(Token.objects.committed()) == 5
    assert all([c.status==Status.COMMITTED for c in Token.objects.committed()])

    '''Checking Tokens by network'''
    assert len(Token.objects.network('Polygon')) == 4
    assert len(Token.objects.network('Ethereum')) == 3
    assert len(Token.objects.network(None)) == 7
    assert not Token.objects.network('Fake')
    assert not Token.objects.network(['Polygon'])
