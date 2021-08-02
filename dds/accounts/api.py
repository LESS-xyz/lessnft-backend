from random import choice
from string import ascii_letters

from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError

from eth_utils.hexadecimal import add_0x_prefix
from eth_account.messages import encode_defunct
from eth_account import Account

from dds.accounts.models import AdvUser
from dds.activity.models import UserAction
from dds.settings import ALLOWED_HOSTS
from dds.utilities import get_media_if_exists

def valid_metamask_message(address, message, signature):
    r = int(signature[0:66], 16)
    s = int(add_0x_prefix(signature[66:130]), 16)
    v = int(add_0x_prefix(signature[130:132]), 16)
    if v not in (27, 28):
        v += 27

    message_hash = encode_defunct(text=message)
    signer_address = Account.recover_message(message_hash, vrs=(v, r, s))
    print(signer_address)
    print(address)

    if signer_address.lower() != address.lower():
        raise ValidationError({'result': 'Incorrect signature'}, code=400)

    return True


@api_view(http_method_names=['GET'])
def generate_metamask_message(request):

    generated_message = ''.join(choice(ascii_letters) for ch in range(30))
    request.session['metamask_message'] = generated_message

    return Response(generated_message)


def user_search(words, page):
    words = words.split(' ')

    users = AdvUser.objects.all()

    for word in words:
        users = users.filter(display_name__icontains=word)

    print(users.__dict__)
    search_result = []
    start = (page - 1) * 50
    end = page * 50 if len(users) >= page * 50 else None

    for user in users[start: end]:
        avatar = get_media_if_exists(user, 'avatar')

        tokens = []
        for token in user.token_owner.all()[:6]:
            t = {
                'id': token.id,
                'media': get_media_if_exists(token, 'media')
            }
            tokens.append(t)
            
        search_result.append({
            'id': user.id,
            'name': user.get_name(),
            'avatar': avatar,
            'followers': user.following.count(),
            'tokens': tokens
        })

    return search_result


def follow_and_follower(user):
    '''
    function for getting who the user is subscribed to and who is subscribed to the user
    '''

    followers, follows = [], []

    # who follow user
    follow_actions = UserAction.objects.filter(method='follow', whom_follow=user)
    followers_queryset = [action.user for action in follow_actions]

    for follower in followers_queryset:
        name = follower.display_name if follower.display_name else follower.username
        followers.append({
            'id': follower.id,
            'name': name, 
            'avatar': ALLOWED_HOSTS[0] + follower.avatar.url,
            'his_followers': len(UserAction.objects.filter(method='follow', whom_follow=follower))
        })

    # user follow
    follow_actions = UserAction.objects.filter(method='follow', user=user)
    follow_queryset = [action.whom_follow for action in follow_actions]

    for follow in follow_queryset:
        name = follow.display_name if follow.display_name else follow.username
        follows.append({
            'id': follow.id,
            'name': name, 
            'avatar': ALLOWED_HOSTS[0] + follow.avatar.url,
            'his_followers': len(UserAction.objects.filter(method='follow', whom_follow=follow))
        })

    return follows, followers
