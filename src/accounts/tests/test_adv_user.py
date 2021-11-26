import pytest

from src.accounts.models import AdvUser


@pytest.mark.django_db
def test_adv_user_manager(mixer):
    mixer.blend(
        'accounts.AdvUser', 
        display_name='testuser',
        custom_url='testurl'
    )

    assert AdvUser.objects.get_by_custom_url('testurl').display_name == 'testuser'
    assert AdvUser.objects.get_by_custom_url(1).display_name == 'testuser'
    assert AdvUser.objects.get_by_custom_url('1').display_name == 'testuser'
