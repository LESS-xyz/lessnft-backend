from django.urls import path
from dds.store.views import *

urlpatterns = [
    path('create_token/', CreateView.as_view()),
    path('save_token/', SaveView.as_view()),
    path('create_collection/', CreateCollectionView.as_view()),
    path('save_collection/', SaveCollectionView.as_view()),
    path('hot/<int:page>/', GetHotView.as_view()),
    path('hot_collections/', GetHotCollectionsView.as_view()),
    path('search/', SearchView.as_view()),
    path('owned/<str:address>/<int:page>/', GetOwnedView.as_view()),
    path('created/<str:address>/<int:page>/', GetCreatedView.as_view()),
    path('liked/<str:address>/<int:page>/', GetLikedView.as_view()),
    path('transfer/<str:token>/', TransferOwned.as_view()),
    path('collection/<int:id>/<int:page>/', GetCollectionView.as_view()),
    path('<int:id>/', GetView.as_view()),
    path('buy/<str:token>/', BuyTokenView.as_view()),
    path('tags/', get_tags),
    path('bids/make_bid/', MakeBid.as_view()),
    path('get_bids/<int:token_id>/<str:auth_token>/', get_bids),
    path('hot_bids/', get_hot_bids),
    path('verificate_bet/<int:token_id>/', VerificateBetView.as_view()),
    path('end_auction/<int:token_id>/', AuctionEndView.as_view()),
    path('report/', ReportView.as_view()),
    path('set_cover/', SetCoverView.as_view()),
    path('fee/', get_fee),
    path('support/', SupportView.as_view()),
]
