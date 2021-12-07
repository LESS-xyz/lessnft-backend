import pytest

from src.accounts.models import AdvUser
from django.core.exceptions import ObjectDoesNotExist

@pytest.mark.django_db
def test_adv_user_manager(mixer):
    adv_user = mixer.blend(
        'accounts.AdvUser', 
        display_name='testuser',
        custom_url='testurl'
    )

    assert AdvUser.objects.get_by_custom_url('testurl').display_name == 'testuser'
    assert AdvUser.objects.get_by_custom_url(adv_user.id).display_name == 'testuser'
    assert AdvUser.objects.get_by_custom_url(str(adv_user.id)).display_name == 'testuser'
    try:
        AdvUser.objects.get_by_custom_url('Fake')
        assert False
    except ObjectDoesNotExist:
        assert True
