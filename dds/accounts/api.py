from random import choice
from string import ascii_letters
from django.db.models import Count

from rest_framework.decorators import api_view
from rest_framework.response import Response

from dds.utilities import get_page_slice
from dds.accounts.models import AdvUser
from dds.accounts.serializers import UserSearchSerializer, FollowerSerializer
from dds.activity.models import UserAction


@api_view(http_method_names=['GET'])
def generate_metamask_message(request):

    generated_message = ''.join(choice(ascii_letters) for ch in range(30))
    request.session['metamask_message'] = generated_message

    return Response(generated_message)


def user_search(words, current_user, **kwargs):
    words = words.split(' ')
    verificated = kwargs.get('verificated')
    order_by = kwargs.get('order_by')
    if order_by:
        reverse = "-" if order_by[0] == "-" else ""

    users = AdvUser.objects.all()

    if verificated is not None:
        users = users.filter(is_verificated=verificated[0].lower()=="true")

    for word in words:
        users = users.filter(display_name__icontains=word)

    if order_by == "created":
        users = users.order_by(f"{reverse}id")
    elif order_by == "followers":
        users = users.annotate(follow_count = Count('following')).order_by(f"{reverse}follow_count")
    elif order_by == "tokens_created":
        users = users.annotate(Count('token_creator')).order_by(f"{reverse}token_creator")

    start, end = get_page_slice(page, len(users))
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
