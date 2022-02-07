import pytest

from src.services.search import SearchCollection
from src.store.models import Status


def collection_assert(method, filter_value, expected_collections):
    search = SearchCollection()
    search.initial()
    getattr(search, method)(filter_value)

    assert sorted(expected_collections) == sorted(
        [collection.name for collection in search.items]
    )


@pytest.mark.parametrize(
    ["filter_value", "expected_collections"],
    [
        (["tag_1"], ["collection_1", "TwoTagsCollection"]),
        (["tag_2"], ["collection_2", "TwoTagsCollection"]),
        (["tag_1,tag_2"], ["collection_1", "collection_2", "TwoTagsCollection"]),
        (
            ["tag_1,tag_2,tag_3"],
            ["collection_1", "collection_2", "collection_3", "TwoTagsCollection"],
        ),
        (["nonexistent,tag_2"], ["collection_2", "TwoTagsCollection"]),
        (["nonexistent"], []),
        ([None], ["collection_1", "collection_2", "collection_3", "TwoTagsCollection"]),
    ],
)
@pytest.mark.django_db
def test_check_search_collection_tags(
    mixer,
    filter_value,
    expected_collections,
):
    tag1, tag2, tag3 = mixer.cycle(3).blend(
        "store.Tags", name=(tag for tag in ("tag_1", "tag_2", "tag_3"))
    )
    col_1, col_2, col_3 = mixer.cycle(3).blend(
        "store.Collection",
        status=Status.COMMITTED,
        name=(name for name in ("collection_1", "collection_2", "collection_3")),
    )
    mixer.cycle(3).blend(
        "store.Token",
        status=Status.COMMITTED,
        tags=(tag for tag in (tag1, tag2, tag3)),
        collection=(collection for collection in (col_1, col_2, col_3)),
        name=(name for name in ("token_1", "token_2", "token_3")),
    )
    col_4 = mixer.blend(
        "store.Collection", status=Status.COMMITTED, name="TwoTagsCollection"
    )
    mixer.cycle(2).blend(
        "store.Token",
        status=Status.COMMITTED,
        tags=(tag for tag in (tag1, tag2)),
        collection=col_4,
    )

    collection_assert("tags", filter_value, expected_collections)


@pytest.mark.parametrize(
    ["filter_value", "expected_collections"],
    [
        (
            [],
            [
                "collection_1",
                "collection_2",
                "collection_3",
                "collection_4",
            ],
        ),
        (["creator_2"], ["collection_1"]),
        (["creator_3"], ["collection_2", "collection_3"]),
        (["creator_1"], []),
        (["fake_creator_url"], []),
    ],
)
@pytest.mark.django_db
def test_search_creator_by_url(
    mixer,
    filter_value,
    expected_collections,
):
    """
    Three collection creators, first of which does not have a custom url,
    and a third having created 2 collections
    """
    creator_1, creator_2, creator_3 = mixer.cycle(3).blend(
        "accounts.AdvUser",
        custom_url=(url for url in (None, "creator_2", "creator_3")),
    )
    mixer.cycle(4).blend(
        "store.Collection",
        status=Status.COMMITTED,
        name=(
            name
            for name in ("collection_1", "collection_2", "collection_3", "collection_4")
        ),
        creator=(creator for creator in (creator_2, creator_3, creator_3, creator_1)),
    )

    collection_assert("creator", filter_value, expected_collections)


@pytest.mark.django_db
def test_search_creator_by_id(mixer):
    """
    Search collection creator by id rather then URL.
    First creator has 2 collections
    """
    creator_1, creator_2, creator_3, creator_4 = mixer.cycle(4).blend(
        "accounts.AdvUser"
    )
    mixer.cycle(5).blend(
        "store.Collection",
        status=Status.COMMITTED,
        name=(
            name
            for name in (
                "collection_4",
                "collection_5",
                "collection_1",
                "collection_2",
                "collection_3",
            )
        ),
        creator=(
            creator
            for creator in (creator_1, creator_1, creator_2, creator_3, creator_4)
        ),
    )

    test_cases = [
        (["collection_4", "collection_5"], [f"{creator_1.id}"]),
        (["collection_1"], [f"{creator_2.id}"]),
        ([], ["invalid"]),
        (
            [
                "collection_1",
                "collection_2",
                "collection_3",
                "collection_4",
                "collection_5",
            ],
            [None],
        ),
    ]

    for case in test_cases:
        collection_assert("creator", case[1], case[0])


@pytest.mark.parametrize(
    ["filter_value", "expected_collections"],
    [
        (["First"], ["FirstCollection"]),
        (["F"], ["FirstCollection", "FiCollection"]),
        (["Second"], ["SecondCollection"]),
        ([""], ["FirstCollection", "FiCollection", "SecondCollection"]),
        (["Collection"], ["FirstCollection", "FiCollection", "SecondCollection"]),
        ([None], ["FirstCollection", "FiCollection", "SecondCollection"]),
        (["F S T"], ["FirstCollection"]),
        (["t o"], ["FirstCollection", "FiCollection", "SecondCollection"]),
        (["x y z"], []),
    ],
)
@pytest.mark.django_db
def test_check_search_collection_text(
    mixer,
    filter_value,
    expected_collections,
):
    mixer.cycle(3).blend(
        "store.Collection",
        status=Status.COMMITTED,
        name=(name for name in ("FirstCollection", "FiCollection", "SecondCollection")),
    )

    collection_assert("text", filter_value, expected_collections)


@pytest.mark.parametrize(
    ["filter_value", "expected_networks"],
    [
        (["Ethereum"], ["Ethereum"]),
        (["Tron"], ["Tron"]),
        (["Ethereum,Tron"], ["Ethereum", "Tron"]),
        (["Polygon,Tron"], ["Tron"]),
        (["Polygon"], []),
        (None, ["Ethereum", "Tron"]),
        (["undefined"], ["Ethereum", "Tron"]),
    ],
)
@pytest.mark.django_db
def test_search_collection_network(
    mixer,
    filter_value,
    expected_networks,
):
    mixer.cycle(2).blend(
        "store.Collection",
        status=Status.COMMITTED,
        network__name=(network for network in ("Ethereum", "Tron")),
    )

    search = SearchCollection()
    search.initial()
    search.network(filter_value)

    assert set(expected_networks) == {
        collection.network.name for collection in search.items
    }
