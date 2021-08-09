from django.urls import path
from dds.accounts.views import *
from dds.accounts.api import generate_metamask_message

urlpatterns = [
    path('metamask_login/', MetamaskLogin.as_view(), name='metamask_login'),
    path('get_metamask_message/', generate_metamask_message),
    path('self/follow/', FollowView.as_view()),
    path('self/unfollow/', UnfollowView.as_view()),
    path('self/like/', LikeView.as_view()),
    path('self/', GetView.as_view()),
    path('<str:string>/collections/', GetUserCollections.as_view()),
    path('following/<str:address>/<int:page>/', GetFollowingView.as_view()),
    path('followers/<str:address>/<int:page>/', GetFollowersView.as_view()),
    path('verification/', VerificationView.as_view()),
    path('set_user_cover/', SetUserCoverView.as_view()),
    path('get_random_cover/', GetRandomCoverView.as_view()),
    path('<str:param>/', GetOtherView.as_view()),
]
