import pytest

from src.store.models import Status, Collection, Token
from src.accounts.models import AdvUser


@pytest.mark.django_db
def test_collection_manager(mixer):
    mixer.blend(
        'accounts.AdvUser', 
        display_name='testuser',
        custom_url='testurl'
    )
    mixer.blend(
        'accounts.AdvUser', 
        display_name='testuser2',
        custom_url='testurl2'
    )

    assert AdvUser.objects.get_by_custom_url('testurl').display_name == 'testuser'
    assert AdvUser.objects.get_by_custom_url(1).display_name == 'testuser'

    assert AdvUser.objects.get_by_custom_url('testurl2').display_name == 'testuser2'
    assert AdvUser.objects.get_by_custom_url(2).display_name == 'testuser2'
