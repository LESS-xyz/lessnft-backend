import pytest

from src.services.search import SearchUser
from src.store.models import Status


def user_assert(method, filter_value, expected_users):
    search = SearchUser()
    search.initial()
    getattr(search, method)(filter_value)

    assert sorted(expected_users) == sorted(
        [user.display_name for user in search.items]
    )


def user_assert_order_by(method, expected_users):
    search = SearchUser()

    search.initial()
    search.order_by(method)

    assert [user.display_name for user in search.items] == expected_users

    search.initial()
    search.order_by("-" + method)

    assert [user.display_name for user in search.items] == expected_users[::-1]


@pytest.mark.parametrize(
    ["filter_value", "expected_users"],
    [
        (["First"], ["FirstName"]),
        (["F"], ["FirstName", "FiName"]),
        (["Second"], ["SecondName"]),
        ([""], ["FirstName", "FiName", "SecondName"]),
        (["name"], ["FirstName", "FiName", "SecondName"]),
        ([None], ["FirstName", "FiName", "SecondName"]),
        (["F S T"], ["FirstName"]),
        (["n m"], ["FirstName", "FiName", "SecondName"]),
        (["x y z"], []),
    ],
)
@pytest.mark.django_db
def test_check_search_user_text(
    mixer,
    filter_value,
    expected_users,
):
    mixer.cycle(3).blend(
        "accounts.AdvUser",
        status=Status.COMMITTED,
        display_name=(name for name in ("FirstName", "FiName", "SecondName")),
    )

    user_assert("text", filter_value, expected_users)


@pytest.mark.parametrize(
    ["filter_value", "expected_users"],
    [
        (["True"], ["verified"]),
        (["true"], ["verified"]),
        (["false"], ["unverified"]),
        (["False"], ["unverified"]),
        (["random_string"], ["unverified"]),
    ],
)
@pytest.mark.django_db
def test_check_search_user_is_verified(
    mixer,
    filter_value,
    expected_users,
):
    mixer.blend("accounts.AdvUser", is_verificated=True, display_name="verified")
    mixer.blend("accounts.AdvUser", is_verificated=False, display_name="unverified")

    user_assert("verificated", filter_value, expected_users)


@pytest.mark.django_db
def test_search_order_by_created(mixer):
    """Check if users are ordered by their creation datetime"""
    mixer.cycle(3).blend(
        "accounts.AdvUser",
        display_name=(name for name in ("first", "second", "third")),
    )
    _list = [
        "first",
        "second",
        "third",
    ]

    user_assert_order_by("created", _list)


@pytest.mark.django_db
def test_search_order_by_followers(mixer):
    """Four users, each having less and less followers"""
    user1, user2, user3, user4 = mixer.cycle(4).blend(
        "accounts.AdvUser",
        display_name=(
            name for name in ("most_followers", "second", "third", "no_followers")
        ),
    )
    mixer.cycle(6).blend(
        "activity.UserAction",
        whom_follow=(follow for follow in (user1, user1, user1, user2, user2, user3)),
        user=(user for user in (user3, user2, user4, user1, user3, user4)),
    )
    _list = [
        "no_followers",
        "third",
        "second",
        "most_followers",
    ]

    user_assert_order_by("followers", _list)


@pytest.mark.django_db
def test_search_order_by_tokens_created(mixer):
    """Four users, each have created less and less tokens than the previous one"""
    user1, user2, user3, _ = mixer.cycle(4).blend(
        "accounts.AdvUser",
        display_name=(
            name for name in ("most_tokens", "second", "third", "least_tokens")
        ),
    )

    mixer.cycle(6).blend(
        "store.Token",
        status=Status.COMMITTED,
        creator=(creator for creator in (user1, user1, user1, user2, user2, user3)),
    )
    _list = [
        "least_tokens",
        "third",
        "second",
        "most_tokens",
    ]

    user_assert_order_by("tokens_created", _list)
