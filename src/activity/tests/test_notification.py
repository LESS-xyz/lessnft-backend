import pytest


@pytest.mark.django_db()
def test_notification(auth_api, api):
    response = api.get("/api/v1/activity/notification/")
    assert response.status_code == 401

    response = auth_api.get("/api/v1/activity/notification/")
    assert response.status_code == 200
