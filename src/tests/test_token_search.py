import json
from datetime import datetime, timedelta

import pytest
from django.utils import timezone

from src.services.search import SearchToken
from src.store.models import Status


def token_assert(method, filter_value, expected_tokens):
    search = SearchToken()
    search.initial()
    getattr(search, method)(filter_value)

    assert sorted(expected_tokens) == sorted([token.name for token in search.items])


def token_assert_order_by(method, expected_tokens):
    search = SearchToken()

    search.initial()
    search.order_by([method])

    assert [token.name for token in search.items] == expected_tokens

    search.initial()
    search.order_by(["-" + method])

    assert [token.name for token in search.items] == expected_tokens[::-1]


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
def test_search_token_network(
    mixer,
    filter_value,
    expected_networks,
):
    col_eth, col_tron, _ = mixer.cycle(3).blend(
        "store.Collection",
        status=Status.COMMITTED,
        network__name=(network for network in ("Ethereum", "Tron", "Polygon")),
    )
    mixer.cycle(2).blend(
        "store.Token",
        collection=(col for col in (col_eth, col_tron)),
        status=Status.COMMITTED,
    )

    search = SearchToken()
    search.initial()
    search.network(filter_value)

    assert set(expected_networks) == {
        token.collection.network.name for token in search.items
    }


@pytest.mark.parametrize(
    ["filter_value", "expected_tokens"],
    [
        (["tag_1"], ["token_1", "TwoTagsToken"]),
        (["tag_2"], ["token_2", "TwoTagsToken"]),
        (["tag_1,tag_2"], ["token_1", "token_2", "TwoTagsToken"]),
        (["tag_1,tag_2,tag_3"], ["token_1", "token_2", "token_3", "TwoTagsToken"]),
        (["nonexistent,tag_2"], ["token_2", "TwoTagsToken"]),
        (["nonexistent"], []),
        ([None], ["token_1", "token_2", "token_3", "TwoTagsToken"]),
    ],
)
@pytest.mark.django_db
def test_check_search_token_tags(
    mixer,
    filter_value,
    expected_tokens,
):
    """Four tokens, each with a tag and a fourth one having 2 tags"""
    tag1, tag2, tag3 = mixer.cycle(3).blend(
        "store.Tags", name=(tag for tag in ("tag_1", "tag_2", "tag_3"))
    )
    mixer.cycle(3).blend(
        "store.Token",
        status=Status.COMMITTED,
        tags=(tag for tag in (tag1, tag2, tag3)),
        name=(name for name in ("token_1", "token_2", "token_3")),
    )
    mixer.blend(
        "store.Token", status=Status.COMMITTED, tags=(tag1, tag2), name="TwoTagsToken"
    )

    token_assert("tags", filter_value, expected_tokens)


@pytest.mark.parametrize(
    ["filter_value", "expected_tokens"],
    [
        (["First"], ["FirstToken"]),
        (["F"], ["FirstToken", "FiToken"]),
        (["Second"], ["SecondToken"]),
        ([""], ["FirstToken", "FiToken", "SecondToken"]),
        (["token"], ["FirstToken", "FiToken", "SecondToken"]),
        ([None], ["FirstToken", "FiToken", "SecondToken"]),
        (["F S T"], ["FirstToken"]),
        (["t o"], ["FirstToken", "FiToken", "SecondToken"]),
        (["x y z"], []),
    ],
)
@pytest.mark.django_db
def test_check_search_token_text(
    mixer,
    filter_value,
    expected_tokens,
):
    mixer.cycle(3).blend(
        "store.Token",
        status=Status.COMMITTED,
        name=(name for name in ("FirstToken", "FiToken", "SecondToken")),
    )

    token_assert("text", filter_value, expected_tokens)


@pytest.mark.parametrize(
    ["filter_value", "expected_tokens"],
    [
        (["True"], ["verified"]),
        (["true"], ["verified"]),
        (["false"], ["unverified"]),
        (["False"], ["unverified"]),
        (["random_string"], ["unverified"]),
    ],
)
@pytest.mark.django_db
def test_check_search_token_is_verified(
    mixer,
    filter_value,
    expected_tokens,
):
    verified_user = mixer.blend("accounts.AdvUser", is_verificated=True)
    unverified_user = mixer.blend("accounts.AdvUser", is_verificated=False)

    mixer.cycle(2).blend(
        "store.Token",
        status=Status.COMMITTED,
        owner=(owner for owner in (verified_user, unverified_user)),
        name=(name for name in ("verified", "unverified")),
    )

    token_assert("is_verified", filter_value, expected_tokens)


@pytest.mark.parametrize(
    ["filter_value", "expected_tokens"],
    [
        ([8], ["Token721_1", "Token721_2", "Token1155"]),
        ([4], ["Token721_1", "Token721_2", "Token1155"]),
        ([3], ["Token721_1", "Token1155"]),
        ([2], ["Token721_1"]),
        ([1], []),
        (None, ["Token721_1", "Token721_2", "Token1155"]),
        (["2"], ["Token721_1"]),
        (["nonvalid"], ["Token721_1", "Token721_2", "Token1155"]),
    ],
)
@pytest.mark.django_db
def test_search_max_price_tokens(
    mixer,
    filter_value,
    expected_tokens,
):
    """Two ERC721 tokens and one ERC1155 with three ownerships, cheapest of which is 2$"""
    usd_rate = mixer.blend("rates.UsdRate", symbol="ETH", rate=1000, decimal=18)

    mixer.cycle(2).blend(
        "store.Token",
        status=Status.COMMITTED,
        currency_price=(price for price in (0.001, 0.003)),
        currency=usd_rate,
        name=(name for name in ("Token721_1", "Token721_2")),
        collection__standart="ERC721",
    )
    token1155 = mixer.blend(
        "store.Token",
        status=Status.COMMITTED,
        currency=usd_rate,
        name="Token1155",
        collection__standart="ERC1155",
    )

    mixer.cycle(3).blend(
        "store.Ownership",
        token=token1155,
        currency_price=(price for price in (0.002, 0.003, 0.007)),
        currency=usd_rate,
        selling=True,
    )

    token_assert("max_price", filter_value, expected_tokens)


@pytest.mark.parametrize(
    ["filter_value", "expected_tokens"],
    [
        ([8], []),
        ([5], ["Token1155"]),
        ([3], ["Token1155"]),
        ([2], ["Token721_2", "Token1155"]),
        (["2"], ["Token721_2", "Token1155"]),
        (None, ["Token721_1", "Token721_2", "Token1155"]),
        ([1], ["Token721_1", "Token721_2", "Token1155"]),
        (["nonvalid"], ["Token721_1", "Token721_2", "Token1155"]),
    ],
)
@pytest.mark.django_db
def test_search_min_price_tokens(
    mixer,
    filter_value,
    expected_tokens,
):
    """Two ERC721 tokens and one ERC1155 with three ownerships, cheapest of which is 2$"""
    usd_rate = mixer.blend("rates.UsdRate", symbol="ETH", rate=1000, decimal=18)

    mixer.cycle(2).blend(
        "store.Token",
        status=Status.COMMITTED,
        currency_price=(price for price in (0.002, 0.003)),
        currency=usd_rate,
        name=(name for name in ("Token721_1", "Token721_2")),
        collection__standart="ERC721",
    )

    token1155 = mixer.blend(
        "store.Token",
        status=Status.COMMITTED,
        currency=usd_rate,
        name="Token1155",
        collection__standart="ERC1155",
    )

    mixer.cycle(3).blend(
        "store.Ownership",
        token=token1155,
        currency_price=(price for price in (0.002, 0.003, 0.007)),
        currency=usd_rate,
        selling=True,
    )

    token_assert("min_price", filter_value, expected_tokens)


@pytest.mark.parametrize(
    ["filter_value", "expected_tokens"],
    [
        (["url_1"], ["token_1"]),
        (["url_2"], ["token_2"]),
        (["url_1,url_2"], ["token_1", "token_2"]),
        ([None], ["token_1", "token_2", "token_3"]),
        (["nonvalid"], []),
    ],
)
@pytest.mark.django_db
def test_search_colections_by_url(
    mixer,
    filter_value,
    expected_tokens,
):
    col_1, col_2, col_3 = mixer.cycle(3).blend(
        "store.Collection",
        status=Status.COMMITTED,
        short_url=(url for url in ("url_1", "url_2", "url_3")),
    )

    mixer.cycle(3).blend(
        "store.Token",
        status=Status.COMMITTED,
        name=(name for name in ("token_1", "token_2", "token_3")),
        collection=(col for col in (col_1, col_2, col_3)),
    )

    token_assert("collections", filter_value, expected_tokens)


@pytest.mark.django_db
def test_search_colections_by_id(mixer):
    col_1, col_2, col_3 = mixer.cycle(3).blend(
        "store.Collection",
        status=Status.COMMITTED,
    )

    mixer.cycle(3).blend(
        "store.Token",
        status=Status.COMMITTED,
        name=(name for name in ("token_1", "token_2", "token_3")),
        collection=(col for col in (col_1, col_2, col_3)),
    )

    test_cases = [
        (["token_1", "token_2"], [f"{col_1.id},{col_2.id}"]),
        (["token_1"], [f"{col_1.id}"]),
        ([], ["invalid"]),
        (["token_1", "token_2", "token_3"], [None]),
    ]

    for case in test_cases:
        token_assert("collections", case[1], case[0])


@pytest.mark.parametrize(
    ["filter_value", "expected_tokens"],
    [
        ([], ["token_1", "token_2"]),
        (["owner_2"], ["token_2", "token_1"]),
        (["owner_1"], ["token_2"]),
        (["fake_owner"], ["token_1", "token_2"]),
        ([None], ["token_1", "token_2"]),
    ],
)
@pytest.mark.django_db
def test_search_owner_by_url(
    mixer,
    filter_value,
    expected_tokens,
):
    owner_1, owner_2 = mixer.cycle(2).blend(
        "accounts.AdvUser", custom_url=(url for url in ("owner_1", "owner_2"))
    )

    mixer.blend("store.Token", status=Status.COMMITTED, name="token_1", owner=owner_2)
    token1155 = mixer.blend("store.Token", status=Status.COMMITTED, name="token_2")

    mixer.cycle(2).blend(
        "store.Ownership",
        token=token1155,
        owner=(owner for owner in (owner_1, owner_2)),
    )

    search = SearchToken()
    search.initial()
    search.owner(filter_value)

    assert set(expected_tokens) == {token.name for token in search.items}


@pytest.mark.django_db
def test_search_owner_by_id(mixer):
    owner_1, owner_2, owner_3 = mixer.cycle(3).blend("accounts.AdvUser")
    mixer.cycle(2).blend(
        "store.Token",
        status=Status.COMMITTED,
        name=(name for name in ("token_1", "token_2")),
        owner=(owner for owner in (owner_2, owner_3)),
    )

    token1155 = mixer.blend("store.Token", status=Status.COMMITTED, name="token_3")
    mixer.cycle(2).blend(
        "store.Ownership",
        token=token1155,
        owner=(owner for owner in (owner_1, owner_2)),
    )

    search = SearchToken()

    test_cases = [
        (["token_3", "token_1"], [f"{owner_2.id}"]),
        (["token_3"], [f"{owner_1.id}"]),
        (["token_3", "token_2", "token_1"], ["invalid"]),
        (["token_3", "token_2", "token_1"], []),
    ]

    for case in test_cases:
        search.initial()
        search.owner(case[1])

        assert set(case[0]) == {token.name for token in search.items}


@pytest.mark.parametrize(
    ["filter_value", "expected_tokens"],
    [
        ([], ["token_1", "token_2", "token_3", "token_4", "token_5"]),
        (["creator_2"], ["token_1"]),
        (["fake_creator"], []),
        ([None], []),
    ],
)
@pytest.mark.django_db
def test_search_creator_by_url(
    mixer,
    filter_value,
    expected_tokens,
):
    creator_1 = mixer.blend(
        "accounts.AdvUser",
    )
    creator_2, creator_3, creator_4 = mixer.cycle(3).blend(
        "accounts.AdvUser",
        custom_url=(url for url in ("creator_2", "creator_3", "creator_4")),
    )
    mixer.cycle(3).blend(
        "store.Token",
        status=Status.COMMITTED,
        name=(name for name in ("token_1", "token_2", "token_3")),
        creator=(creator for creator in (creator_2, creator_3, creator_4)),
    )
    mixer.cycle(2).blend(
        "store.Token",
        status=Status.COMMITTED,
        name=(name for name in ("token_4", "token_5")),
        creator=creator_1,
    )

    token_assert("creator", filter_value, expected_tokens)


@pytest.mark.django_db
def test_search_creator_by_id(mixer):
    creator_1, creator_2 = mixer.cycle(2).blend(
        "accounts.AdvUser",
    )
    mixer.cycle(2).blend(
        "store.Token",
        status=Status.COMMITTED,
        name=(name for name in ("token_1", "token_2")),
        creator=(creator for creator in (creator_1, creator_2)),
    )
    mixer.cycle(2).blend(
        "store.Token",
        status=Status.COMMITTED,
        name=(name for name in ("token_3", "token_4")),
        creator=creator_1,
    )

    test_cases = [
        ([], ["token_1", "token_2", "token_3", "token_4"]),
        ([f"{creator_2.id}"], ["token_2"]),
        ([f"{creator_1.id}"], ["token_1", "token_3", "token_4"]),
    ]

    for case in test_cases:
        token_assert("creator", case[0], case[1])


@pytest.mark.parametrize(
    ["filter_value", "expected_tokens"],
    [
        ([], ["token_1", "token_2", "token_3", "token_4"]),
        (["ETH"], ["token_1"]),
        (["BNB"], ["token_2", "token_4"]),
        (["ETH,BNB"], ["token_1", "token_2", "token_4"]),
        (["Tron"], ["token_3"]),
        (["fake_currency"], []),
    ],
)
@pytest.mark.django_db
def test_search_currency(
    mixer,
    filter_value,
    expected_tokens,
):
    eth, bnb, tron = mixer.cycle(3).blend(
        "rates.UsdRate",
        symbol=(symbol for symbol in ("ETH", "BNB", "Tron")),
    )

    mixer.cycle(3).blend(
        "store.Token",
        status=Status.COMMITTED,
        currency=(currency for currency in (eth, bnb, tron)),
        name=(name for name in ("token_1", "token_2", "token_3")),
    )
    mixer.blend(
        "store.Token",
        status=Status.COMMITTED,
        currency=bnb,
        name="token_4",
    )

    token_assert("currency", filter_value, expected_tokens)


@pytest.mark.parametrize(
    ["filter_value", "expected_tokens"],
    [
        ([""], ["Token1155", "Token721_1", "Token721_2"]),
        (["true"], ["Token1155", "Token721_1"]),
        (["false"], ["Token721_2"]),
        ([None], ["Token1155", "Token721_1", "Token721_2"]),
    ],
)
@pytest.mark.django_db
def test_search_on_sale(
    mixer,
    filter_value,
    expected_tokens,
):
    usd_rate = mixer.blend("rates.UsdRate", symbol="ETH", rate=1000, decimal=18)

    mixer.blend(
        "store.Token",
        status=Status.COMMITTED,
        currency_price=0.002,
        currency=usd_rate,
        selling=True,
        name="Token721_1",
        collection__standart="ERC721",
    )
    mixer.blend(
        "store.Token",
        status=Status.COMMITTED,
        currency_price=0.003,
        currency=usd_rate,
        name="Token721_2",
        selling=False,
    )

    token1155 = mixer.blend(
        "store.Token",
        status=Status.COMMITTED,
        currency=usd_rate,
        name="Token1155",
        collection__standart="ERC1155",
    )

    mixer.cycle(3).blend(
        "store.Ownership",
        token=token1155,
        currency_price=(price for price in (0.002, 0.003, 0.007)),
        currency=usd_rate,
        selling=True,
    )

    token_assert("on_sale", filter_value, expected_tokens)


@pytest.mark.parametrize(
    ["filter_value", "expected_tokens"],
    [
        ([""], ["Token1155", "Token721_1", "Token721_2"]),
        (["true"], ["Token1155", "Token721_1"]),
        (["false"], ["Token721_2"]),
        (["random_string"], ["Token721_2"]),
        ([None], ["Token1155", "Token721_1", "Token721_2"]),
    ],
)
@pytest.mark.django_db
def test_search_on_auc_sale(
    mixer,
    filter_value,
    expected_tokens,
):
    usd_rate = mixer.blend("rates.UsdRate", symbol="ETH", rate=1000, decimal=18)

    mixer.cycle(2).blend(
        "store.Token",
        status=Status.COMMITTED,
        currency=usd_rate,
        selling=(selling for selling in (True, False)),
        name=(name for name in ("Token721_1", "Token721_2")),
        collection__standart="ERC721",
        currency_minimal_bid=0.001,
    )

    token1155 = mixer.blend(
        "store.Token",
        status=Status.COMMITTED,
        currency=usd_rate,
        name="Token1155",
        collection__standart="ERC1155",
    )

    mixer.blend(
        "store.Ownership",
        token=token1155,
        currency=usd_rate,
        selling=True,
        currency_minimal_bid=0.003,
    )

    token_assert("on_auc_sale", filter_value, expected_tokens)


@pytest.mark.parametrize(
    ["filter_value", "expected_tokens"],
    [
        (["true"], ["Token721_1", "Token1155"]),
        (["false"], ["Token721_2", "Future_sale"]),
        (["random_string"], ["Token721_2", "Future_sale"]),
    ],
)
@pytest.mark.django_db
def test_search_on_timed_auc_sale(
    mixer,
    filter_value,
    expected_tokens,
):
    """
    Checking if a token if on a timed auction with three auctions which will
    end in the far future and one auction which will only start in the future
    """
    usd_rate = mixer.blend("rates.UsdRate", symbol="ETH", rate=1000, decimal=18)

    """ Two tokens with auctions which will end far in the future """

    mixer.cycle(2).blend(
        "store.Token",
        status=Status.COMMITTED,
        currency=usd_rate,
        selling=(selling for selling in (True, False)),
        name=(name for name in ("Token721_1", "Token721_2")),
        currency_minimal_bid=0.001,
        start_auction=timezone.make_aware(datetime.fromtimestamp(0)),
        end_auction=timezone.make_aware(datetime.fromtimestamp(10000000000)),
    )

    """ Token with an auction which hasn't started yet """

    mixer.blend(
        "store.Token",
        status=Status.COMMITTED,
        currency=usd_rate,
        selling=True,
        name="Future_sale",
        currency_minimal_bid=0.001,
        start_auction=timezone.make_aware(datetime.now() + timedelta(days=1)),
        end_auction=timezone.make_aware(datetime.now() + timedelta(days=2)),
    )

    """ Same as the first two tokens, but erc1155 """

    token1155 = mixer.blend(
        "store.Token",
        status=Status.COMMITTED,
        currency=usd_rate,
        name="Token1155",
        collection__standart="ERC1155",
        start_auction=timezone.make_aware(datetime.fromtimestamp(0)),
        end_auction=timezone.make_aware(datetime.fromtimestamp(10000000000)),
    )

    mixer.blend(
        "store.Ownership",
        token=token1155,
        currency=usd_rate,
        selling=True,
        currency_minimal_bid=0.003,
    )

    token_assert("on_timed_auc_sale", filter_value, expected_tokens)


@pytest.mark.parametrize(
    ["filter_value", "expected_tokens"],
    [
        (["true"], ["Token721_1", "Token1155"]),
        (["false"], ["Token721_2"]),
        (["random_string"], ["Token721_2"]),
    ],
)
@pytest.mark.django_db
def test_search_has_bids(
    mixer,
    filter_value,
    expected_tokens,
):
    """Checking if tokens have bids with three auctions which will end in the far future"""

    usd_rate = mixer.blend("rates.UsdRate", symbol="ETH", rate=1000, decimal=18)

    """ Two tokens with auctions which will end far in the future """

    token_1, _ = mixer.cycle(2).blend(
        "store.Token",
        status=Status.COMMITTED,
        currency=usd_rate,
        selling=True,
        name=(name for name in ("Token721_1", "Token721_2")),
        currency_minimal_bid=0.001,
        start_auction=timezone.make_aware(datetime.fromtimestamp(0)),
        end_auction=timezone.make_aware(datetime.fromtimestamp(10000000000)),
    )

    """ Same as the first two tokens, but erc1155 """

    token1155 = mixer.blend(
        "store.Token",
        status=Status.COMMITTED,
        currency=usd_rate,
        name="Token1155",
        collection__standart="ERC1155",
        start_auction=timezone.make_aware(datetime.fromtimestamp(0)),
        end_auction=timezone.make_aware(datetime.fromtimestamp(10000000000)),
    )
    mixer.blend(
        "store.Ownership",
        token=token1155,
        currency=usd_rate,
        selling=True,
        currency_minimal_bid=0.003,
    )

    mixer.cycle(2).blend(
        "store.Bid",
        state=Status.COMMITTED,
        quantity=1,
        token=(token for token in (token_1, token1155)),
    )

    token_assert("has_bids", filter_value, expected_tokens)


@pytest.mark.parametrize(
    ["filter_value", "expected_tokens"],
    [
        (["user_1"], ["Token721_1", "Token1155"]),
        (["user_2"], ["Token721_2"]),
        (["nonvalid"], ["Token721_1", "Token721_2", "Token1155"]),
    ],
)
@pytest.mark.django_db
def test_search_bids_by_url(
    mixer,
    filter_value,
    expected_tokens,
):
    """Checking tokens by bids urls with three auctions which will end in the far future"""

    usd_rate = mixer.blend("rates.UsdRate", symbol="ETH", rate=1000, decimal=18)
    user_1, user_2, = mixer.cycle(2).blend(
        "accounts.AdvUser",
        custom_url=(url for url in ("user_1", "user_2")),
        is_verificated=True,
    )

    """ Two tokens with auctions which will end far in the future """

    token_1, token_2 = mixer.cycle(2).blend(
        "store.Token",
        status=Status.COMMITTED,
        currency=usd_rate,
        selling=True,
        name=(name for name in ("Token721_1", "Token721_2")),
        currency_minimal_bid=0.001,
        start_auction=timezone.make_aware(datetime.fromtimestamp(0)),
        end_auction=timezone.make_aware(datetime.fromtimestamp(10000000000)),
    )

    """ Same as the first two tokens, but erc1155 """

    token1155 = mixer.blend(
        "store.Token",
        status=Status.COMMITTED,
        currency=usd_rate,
        name="Token1155",
        collection__standart="ERC1155",
        start_auction=timezone.make_aware(datetime.fromtimestamp(0)),
        end_auction=timezone.make_aware(datetime.fromtimestamp(10000000000)),
    )

    mixer.cycle(3).blend(
        "store.Bid",
        state=Status.COMMITTED,
        quantity=1,
        user=(user for user in (user_1, user_1, user_2)),
        token=(token for token in (token_1, token1155, token_2)),
    )

    token_assert("bids_by", filter_value, expected_tokens)


@pytest.mark.django_db
def test_search_bids_by_id(mixer):
    """Same as above, but checking by ids"""

    usd_rate = mixer.blend("rates.UsdRate", symbol="ETH", rate=1000, decimal=18)
    user_1, user_2 = mixer.cycle(2).blend("accounts.AdvUser", is_verificated=True)

    token_1, token_2 = mixer.cycle(2).blend(
        "store.Token",
        status=Status.COMMITTED,
        currency=usd_rate,
        selling=True,
        name=(name for name in ("Token721_1", "Token721_2")),
        currency_minimal_bid=0.001,
        start_auction=timezone.make_aware(datetime.fromtimestamp(0)),
        end_auction=timezone.make_aware(datetime.fromtimestamp(10000000000)),
    )
    token1155 = mixer.blend(
        "store.Token",
        status=Status.COMMITTED,
        currency=usd_rate,
        name="Token1155",
        collection__standart="ERC1155",
        start_auction=timezone.make_aware(datetime.fromtimestamp(0)),
        end_auction=timezone.make_aware(datetime.fromtimestamp(10000000000)),
    )

    mixer.cycle(3).blend(
        "store.Bid",
        state=Status.COMMITTED,
        quantity=1,
        user=(user for user in (user_1, user_1, user_2)),
        token=(token for token in (token_1, token1155, token_2)),
    )

    test_cases = [
        (["Token1155", "Token721_1"], [f"{user_1.id}"]),
        (["Token721_2"], [f"{user_2.id}"]),
        (["Token1155", "Token721_2", "Token721_1"], [""]),
        (["Token1155", "Token721_2", "Token721_1"], ["nonvalid"]),
    ]

    for case in test_cases:
        token_assert("bids_by", case[1], case[0])


@pytest.mark.parametrize(
    ["filter_value", "expected_tokens"],
    [
        ({"TRAIT_1": {"min": 3, "max": 3}}, ["token_1", "token_3"]),
        (
            {"TRAIT_1": {"min": 3, "max": 3}, "TRAIT_2": {"min": 3, "max": 3}},
            ["token_1"],
        ),
        ({"TRAIT_1": {"min": 1, "max": 1}}, ["token_2"]),
        ({"TRAIT_3": {"min": 1, "max": 8}}, ["token_4"]),
        ({"Invalid_trait": {"min": 1, "max": 8}}, []),
    ],
)
@pytest.mark.django_db
def test_check_search_token_stats(
    mixer,
    filter_value,
    expected_tokens,
):
    """
    Finding tokens with four different stats by the stat's min and max values,
    first token has a stat with 2 traits
    """
    stats = (
        {
            "TRAIT_1": {
                "value": 3,
                "max_value": 4,
                "trait_type": "TRATI_1",
                "display_type": "stats",
            },
            "TRAIT_2": {
                "value": 3,
                "max_value": 5,
                "trait_type": "TRAIT_2",
                "display_type": "stats",
            },
        },
        {
            "TRAIT_1": {
                "value": 1,
                "max_value": 1,
                "trait_type": "TRAIT_1",
                "display_type": "stats",
            }
        },
        {
            "TRAIT_1": {
                "value": 3,
                "max_value": 5,
                "trait_type": "TRAIT_1",
                "display_type": "stats",
            }
        },
        {
            "TRAIT_3": {
                "value": 2,
                "max_value": 5,
                "trait_type": "TRAIT_1",
                "display_type": "stats",
            }
        },
    )

    mixer.cycle(4).blend(
        "store.Token",
        status=Status.COMMITTED,
        _stats=(stat for stat in stats),
        name=(name for name in ("token_1", "token_2", "token_3", "token_4")),
    )

    token_assert("stats", [json.dumps(filter_value)], expected_tokens)


@pytest.mark.parametrize(
    ["filter_value", "expected_tokens"],
    [
        ({"TRAIT_1": {"min": 3, "max": 3}}, ["token_1", "token_3"]),
        (
            {"TRAIT_1": {"min": 3, "max": 3}, "TRAIT_2": {"min": 3, "max": 3}},
            ["token_1"],
        ),
        ({"TRAIT_1": {"min": 1, "max": 1}}, ["token_2"]),
        ({"TRAIT_3": {"min": 1, "max": 8}}, ["token_4"]),
        ({"Invalid_trait": {"min": 1, "max": 8}}, []),
    ],
)
@pytest.mark.django_db
def test_check_search_token_rankings(
    mixer,
    filter_value,
    expected_tokens,
):
    """
    Finding tokens with four different rankings by the trait's min and max values,
    first token has a rank with 2 traits
    """

    ranks = (
        {
            "TRAIT_1": {
                "value": 3,
                "max_value": 5,
                "trait_type": "TRATI_1",
                "display_type": "rankings",
            },
            "TRAIT_2": {
                "value": 3,
                "max_value": 5,
                "trait_type": "TRAIT_2",
                "display_type": "rankings",
            },
        },
        {
            "TRAIT_1": {
                "value": 1,
                "max_value": 1,
                "trait_type": "TRAIT_1",
                "display_type": "rankings",
            }
        },
        {
            "TRAIT_1": {
                "value": 3,
                "max_value": 5,
                "trait_type": "TRAIT_1",
                "display_type": "rankings",
            }
        },
        {
            "TRAIT_3": {
                "value": 2,
                "max_value": 5,
                "trait_type": "TRAIT_1",
                "display_type": "rankings",
            }
        },
    )
    mixer.cycle(4).blend(
        "store.Token",
        status=Status.COMMITTED,
        _rankings=(ranks for ranks in ranks),
        name=(name for name in ("token_1", "token_2", "token_3", "token_4")),
    )

    token_assert("rankings", [json.dumps(filter_value)], expected_tokens)


@pytest.mark.parametrize(
    ["filter_value", "expected_tokens"],
    [
        ({"TRAIT_1": ["value_1", "value_4"]}, ["token_1", "token_2"]),
        ({"TRAIT_2": ["value_2"]}, ["token_1"]),
        ({"TRAIT_4": ["value_4"]}, []),
        ({"TRAIT_3": ["value_3"]}, ["token_3"]),
        ({"TRAIT_1": ["value_1", "value_5"]}, ["token_1", "token_2", "token_4"]),
        ({"Invalid_trait": ["value_1", "value_5"]}, []),
    ],
)
@pytest.mark.django_db
def test_check_search_token_properties(
    mixer,
    filter_value,
    expected_tokens,
):
    """
    Finding tokens with four different properties by the trait's values,
    first token has a property with 2 traits
    """
    props = (
        {
            "TRAIT_1": {
                "value": "value_1",
                "trait_type": "TRAIT_1",
                "display_type": "properties",
            },
            "TRAIT_2": {
                "value": "value_2",
                "trait_type": "TRAIT_2",
                "display_type": "properties",
            },
        },
        {
            "TRAIT_1": {
                "value": "value_1",
                "trait_type": "TRAIT_1",
                "display_type": "properties",
            }
        },
        {
            "TRAIT_3": {
                "value": "value_3",
                "trait_type": "TRAIT_3",
                "display_type": "properties",
            }
        },
        {
            "TRAIT_1": {
                "value": "value_5",
                "trait_type": "TRAIT_1",
                "display_type": "properties",
            }
        },
    )
    mixer.cycle(4).blend(
        "store.Token",
        status=Status.COMMITTED,
        _properties=(prop for prop in props),
        name=(name for name in ("token_1", "token_2", "token_3", "token_4")),
    )

    token_assert("properties", [json.dumps(filter_value)], expected_tokens)


@pytest.mark.django_db
def test_search_order_by_price(mixer):
    """Four tokens, 3 ERC721, one of which is not selling, and ERC1155, which is second most expensive"""

    usd_rate = mixer.blend("rates.UsdRate", symbol="ETH", rate=1000, decimal=18)
    mixer.cycle(3).blend(
        "store.Token",
        status=Status.COMMITTED,
        currency_price=(price for price in (0.001, None, 0.006)),
        currency=usd_rate,
        selling=(selling for selling in (True, False, True)),
        name=(name for name in ("cheapest", "not_selling", "most_expensive")),
        collection__standart="ERC721",
    )
    second_1155 = mixer.blend(
        "store.Token",
        status=Status.COMMITTED,
        currency=usd_rate,
        name="second_1155",
        collection__standart="ERC1155",
    )
    """ 
    Three ownerships of token 1155, with the least expensive (0.002) 
    making token 1155 second most expensive out of the three tokens
    """
    mixer.cycle(3).blend(
        "store.Ownership",
        token=second_1155,
        currency_price=(price for price in (0.002, 0.003, 0.007)),
        currency=usd_rate,
        selling=True,
    )
    _list = [
        "not_selling",
        "cheapest",
        "second_1155",
        "most_expensive",
    ]

    token_assert_order_by("price", _list)


@pytest.mark.django_db
def test_search_order_by_likes(mixer):
    """
    Four tokens, 3 ERC721, one of which has no likes,
    and ERC1155, which is the second most liked
    """
    most_liked, third, _ = mixer.cycle(3).blend(
        "store.Token",
        status=Status.COMMITTED,
        name=(name for name in ("most_liked", "third", "least_liked")),
        collection__standart="ERC721",
    )
    second_1155 = mixer.blend(
        "store.Token",
        status=Status.COMMITTED,
        name="second_1155",
        collection__standart="ERC1155",
    )
    mixer.cycle(6).blend(
        "activity.UserAction",
        method="like",
        token=(
            token
            for token in (
                most_liked,
                most_liked,
                most_liked,
                second_1155,
                second_1155,
                third,
            )
        ),
    )
    _list = [
        "least_liked",
        "third",
        "second_1155",
        "most_liked",
    ]

    token_assert_order_by("likes", _list)


@pytest.mark.django_db
def test_search_order_by_created_at(mixer):
    dates = [
        timezone.make_aware(datetime.fromtimestamp(10000000000)),
        timezone.make_aware(datetime.fromtimestamp(1000000000)),
        timezone.make_aware(datetime.fromtimestamp(100000000)),
        timezone.make_aware(datetime.fromtimestamp(10000000)),
    ]
    mixer.cycle(3).blend(
        "store.Token",
        status=Status.COMMITTED,
        name=(name for name in ("latest", "third", "second")),
        collection__standart="ERC721",
        updated_at=(date for date in dates),
    )
    mixer.blend(
        "store.Token",
        status=Status.COMMITTED,
        name="earliest",
        collection__standart="ERC1155",
        updated_at=dates[3],
    )
    _list = [
        "latest",
        "third",
        "second",
        "earliest",
    ]

    token_assert_order_by("created_at", _list)


@pytest.mark.django_db
def test_search_order_by_views(mixer):
    """
    Four tokens, 3 ERC721, one of which has never been viewed,
    and ERC1155, which is the third most viewed
    """
    most_viewed, second, _ = mixer.cycle(3).blend(
        "store.Token",
        status=Status.COMMITTED,
        name=(name for name in ("most_viewed", "second", "least_viewed")),
        collection__standart="ERC721",
    )
    third_1155 = mixer.blend(
        "store.Token",
        status=Status.COMMITTED,
        name="third",
        collection__standart="ERC1155",
    )

    mixer.cycle(6).blend(
        "store.ViewsTracker",
        token=(
            token
            for token in (
                most_viewed,
                most_viewed,
                most_viewed,
                second,
                second,
                third_1155,
            )
        ),
    )
    _list = [
        "least_viewed",
        "third",
        "second",
        "most_viewed",
    ]

    token_assert_order_by("views", _list)


@pytest.mark.django_db
def test_search_order_by_sale(mixer):
    """
    Four tokens, 3 ERC721, one of which has never been bought,
    and ERC1155, which is the third most recently bought
    """
    most_recent, second, _ = mixer.cycle(3).blend(
        "store.Token",
        status=Status.COMMITTED,
        name=(name for name in ("most_recent", "second", "never_bought")),
        collection__standart="ERC721",
    )
    third_1155 = mixer.blend(
        "store.Token",
        status=Status.COMMITTED,
        name="third",
        collection__standart="ERC1155",
    )
    mixer.cycle(3).blend(
        "activity.TokenHistory",
        token=(token for token in (third_1155, second, most_recent)),
        method="Buy",
    )
    _list = [
        "never_bought",
        "third",
        "second",
        "most_recent",
    ]

    token_assert_order_by("sale", _list)


@pytest.mark.django_db
def test_search_order_by_transfer(mixer):
    """
    Four tokens, 3 ERC721, one of which has never been transfered,
    and ERC1155, which is the third most recently transfered
    """
    most_recent, second, _ = mixer.cycle(3).blend(
        "store.Token",
        status=Status.COMMITTED,
        name=(name for name in ("most_recent", "second", "never_transfered")),
        collection__standart="ERC721",
    )
    third_1155 = mixer.blend(
        "store.Token",
        status=Status.COMMITTED,
        name="third",
        collection__standart="ERC1155",
    )

    mixer.cycle(3).blend(
        "activity.TokenHistory",
        token=(token for token in (third_1155, second, most_recent)),
        method="Transfer",
    )
    _list = [
        "never_transfered",
        "third",
        "second",
        "most_recent",
    ]

    token_assert_order_by("transfer", _list)


@pytest.mark.django_db
def test_search_order_by_auction_end(mixer):
    """
    Four tokens, from the latest to the earisest auction time, the last of
    which, ERC1155-standart token, has no auction at all
    """
    usd_rate = mixer.blend("rates.UsdRate", symbol="ETH", rate=1000, decimal=18)
    dates = [
        timezone.make_aware(datetime.fromtimestamp(30000000000)),
        timezone.make_aware(datetime.fromtimestamp(20000000000)),
        timezone.make_aware(datetime.fromtimestamp(10000000000)),
    ]

    mixer.cycle(3).blend(
        "store.Token",
        status=Status.COMMITTED,
        currency=usd_rate,
        selling=True,
        name=(name for name in ("latest", "second", "third")),
        currency_minimal_bid=0.001,
        start_auction=timezone.now(),
        end_auction=(date for date in dates),
        collection__standart="ERC721",
    )
    mixer.blend(
        "store.Token",
        status=Status.COMMITTED,
        currency=usd_rate,
        name="no_auction",
        collection__standart="ERC1155",
    )
    _list = [
        "no_auction",
        "third",
        "second",
        "latest",
    ]

    token_assert_order_by("auction_end", _list)


@pytest.mark.django_db
def test_search_order_by_last_sale(mixer):
    """
    Four tokens 3 ERC721, from cheapest to most expensive,
    one of which has never been sold, and ERC1155,
    which is the most expensive
    """
    cheapest, second, _ = mixer.cycle(3).blend(
        "store.Token",
        status=Status.COMMITTED,
        name=(name for name in ("cheapest", "second", "never_bought")),
        collection__standart="ERC721",
    )
    third_1155 = mixer.blend(
        "store.Token",
        status=Status.COMMITTED,
        name="most_expensive",
        collection__standart="ERC1155",
    )
    """ 
    "Buy" events, with second most expensive token getting cheaper and
    most expensive token getting more expensive 
    """
    mixer.cycle(6).blend(
        "activity.TokenHistory",
        token=(
            token
            for token in (cheapest, second, second, third_1155, third_1155, third_1155)
        ),
        method="Buy",
        price=(price for price in (0.002, 0.005, 0.003, 0.003, 0.004, 0.005)),
    )
    _list = [
        "never_bought",
        "cheapest",
        "second",
        "most_expensive",
    ]

    token_assert_order_by("sale", _list)
