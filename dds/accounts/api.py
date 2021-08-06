from random import choice
from string import ascii_letters

from rest_framework.decorators import api_view
from rest_framework.response import Response

from dds.accounts.models import AdvUser
from dds.accounts.serializers import UserSearchSerializer, FollowerSerializer
from dds.activity.models import UserAction


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
    start = (page - 1) * 50
    end = page * 50 if len(users) >= page * 50 else None
    return UserSearchSerializer(users[start:end], many=True).data


def follow_and_follower(user):
    '''
    function for getting who the user is subscribed to and who is subscribed to the user
    '''

    # who follow user
    follow_actions = UserAction.objects.filter(method='follow', whom_follow=user)
    followers_queryset = [action.user for action in follow_actions]
    followers = FollowerSerializer(followers_queryset, many=True).data

    # user follow
    follow_actions = UserAction.objects.filter(method='follow', user=user)
    follow_queryset = [action.whom_follow for action in follow_actions]
    follows = FollowerSerializer(follow_queryset, many=True).data

    return follows, followers
