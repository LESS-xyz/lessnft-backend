from django.urls import path

from src.accounts.api import generate_metamask_message
from src.accounts.views import (
    FollowView,
    GetFollowersView,
    GetFollowingView,
    GetOtherView,
    GetRandomCoverView,
    GetUserCollections,
    GetView,
    LikeView,
    MetamaskLogin,
    SaveEmail,
    SetUserCoverView,
    UnfollowView,
    VerificationView,
)

urlpatterns = [
    path("metamask_login/", MetamaskLogin.as_view(), name="metamask_login"),
    path("get_metamask_message/", generate_metamask_message),
    path("self/follow/", FollowView.as_view()),
    path("self/unfollow/", UnfollowView.as_view()),
    path("self/like/", LikeView.as_view()),
    path("self/collections/", GetUserCollections.as_view()),
    path("self/", GetView.as_view()),
    path("following/<str:address>/", GetFollowingView.as_view()),
    path("followers/<str:address>/", GetFollowersView.as_view()),
    path("verification/", VerificationView.as_view()),
    path("set_user_cover/", SetUserCoverView.as_view()),
    path("get_random_cover/", GetRandomCoverView.as_view()),
    path("save_email/", SaveEmail.as_view()),
    path("<str:param>/", GetOtherView.as_view()),
]
