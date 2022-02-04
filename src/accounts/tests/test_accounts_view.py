import pytest

from src.activity.models import UserAction
from src.store.models import Status


@pytest.mark.django_db
def test_self_view_get(api, auth_api):
    URL = "/api/v1/account/self/"
    response = auth_api.get(URL)
    assert response.status_code == 200
    assert response.json().get("display_name") == "Rodion"

    response = api.get(URL)
    assert response.status_code == 401


@pytest.mark.django_db
def test_self_view_patch(api, auth_api):
    URL = "/api/v1/account/self/"
    response = auth_api.patch(URL, data={"display_name": "Kubernetes"})
    assert response.status_code == 200
    assert response.json().get("display_name") == "Kubernetes"

    response = auth_api.patch(URL, data={"display_name": "not valid length" * 20})
    assert response.status_code == 400

    response = api.patch(URL, data={"display_name": "Kubernetes"})
    assert response.status_code == 401


@pytest.mark.django_db
def test_get_other_view(mixer, api):
    URL = "/api/v1/account/{user}/"
    user = mixer.blend("accounts.AdvUser", custom_url="other_man")

    response = api.get(URL.format(user=user.id))
    assert response.status_code == 200
    assert response.json().get("id") == user.custom_url

    response = api.get(URL.format(user=user.custom_url))
    assert response.status_code == 200
    assert response.json().get("id") == user.custom_url

    response = api.get(URL.format(user="non-exists-user"))
    assert response.status_code == 404


@pytest.mark.django_db
def test_follow_view(mixer, api, auth_api):
    URL = "/api/v1/account/self/follow/"
    user = mixer.blend("accounts.AdvUser", custom_url="follower")

    assert not UserAction.objects.filter(user=auth_api.user, whom_follow=user).exists()
    response = auth_api.post(URL, data={"id": user.id})
    assert response.status_code == 200
    assert UserAction.objects.filter(user=auth_api.user, whom_follow=user).exists()

    response = auth_api.post(URL, data={"id": auth_api.user.id})
    assert response.status_code == 400

    response = api.post(URL, data={"id": 99})
    assert response.status_code == 401


@pytest.mark.django_db
def test_unfollow_view(mixer, api, auth_api):
    URL = "/api/v1/account/self/unfollow/"
    user = mixer.blend("accounts.AdvUser", custom_url="unfollower")
    mixer.blend("activity.UserAction", user=auth_api.user, whom_follow=user)

    response = auth_api.post(URL, data={"id": user.id})
    assert response.status_code == 200
    assert not UserAction.objects.filter(user=auth_api.user, whom_follow=user).exists()

    response = auth_api.post(URL, data={"id": user.id})
    assert response.status_code == 200

    response = api.post(URL, data={"id": 99})
    assert response.status_code == 401


@pytest.mark.django_db
def test_like_view(mixer, api, auth_api):
    URL = "/api/v1/account/self/like/"
    token = mixer.blend("store.Token", status=Status.COMMITTED)

    response = auth_api.post(URL, data={"id": token.id})
    assert response.status_code == 200
    assert UserAction.objects.filter(
        user=auth_api.user,
        whom_follow=None,
        method="like",
        token=token,
    ).exists()

    response = auth_api.post(URL, data={"id": token.id})
    assert response.status_code == 200
    assert not UserAction.objects.filter(
        user=auth_api.user,
        whom_follow=None,
        method="like",
        token=token,
    ).exists()

    response = api.post(URL, data={"id": 99})
    assert response.status_code == 401

    response = auth_api.post(URL, data={"id": 0})
    assert response.status_code == 404


@pytest.mark.django_db
def test_get_user_collections_view(mixer, api, auth_api):
    URL = "/api/v1/account/self/collections/"
    col_eth, col_tron = mixer.cycle(2).blend(
        "store.Collection",
        status=Status.COMMITTED,
        creator=auth_api.user,
        network__name=(network for network in ("Ethereum", "Tron")),
    )
    mixer.blend(
        "store.Collection",
        status=Status.PENDING,
        creator=auth_api.user,
        network__name="Ethereum",
    )

    response = auth_api.get(URL)
    assert response.status_code == 200
    assert [col["id"] for col in response.json().get("results")] == [
        col_eth.id,
        col_tron.id,
    ]

    response = auth_api.get(URL, data={"network": "Ethereum"})
    assert response.status_code == 200
    assert len(response.json().get("results")) == 1
    assert response.json().get("results")[0]["id"] == col_eth.id

    response = api.get(URL)
    assert response.status_code == 401


@pytest.mark.django_db
def test_following_view(mixer, api):
    URL = "/api/v1/account/following/{user}/"
    user = mixer.blend("accounts.AdvUser")
    mixer.cycle(3).blend(
        "activity.UserAction",
        user=user,
        method="follow",
    )
    mixer.cycle(2).blend(
        "activity.UserAction",
        whom_follow=user,
        method="follow",
    )

    response = api.get(URL.format(user=user.id))
    assert response.status_code == 200
    assert len(response.json().get("results")) == 3

    response = api.get(URL.format(user=0))
    assert response.status_code == 404


@pytest.mark.django_db
def test_followers_view(mixer, api):
    URL = "/api/v1/account/followers/{user}/"
    user = mixer.blend("accounts.AdvUser")
    mixer.cycle(3).blend(
        "activity.UserAction",
        whom_follow=user,
        method="follow",
    )
    mixer.blend(
        "activity.UserAction",
        user=user,
        method="follow",
    )

    response = api.get(URL.format(user=user.id))
    assert response.status_code == 200
    assert len(response.json().get("results")) == 3

    response = api.get(URL.format(user=0))
    assert response.status_code == 404


@pytest.mark.django_db
def test_save_email_view(mixer, api):
    URL = "/api/v1/account/save_email/"
    mail = "rodion@k8s.net"

    response = api.post(URL, data={"address": mail})
    assert response.status_code == 201

    response = api.post(URL, data={"address": mail})
    assert response.status_code == 400
