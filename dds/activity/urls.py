from django.urls import path
from dds.activity import views


urlpatterns = [
    path('topusers/', views.GetBestDealView.as_view()),
    path('notification/', views.NotificationActivityView.as_view()),
    path('', views.ActivityView.as_view()),
    path('<str:address>/', views.UserActivityView.as_view()),
    path('<str:address>/following/', views.FollowingActivityView.as_view()),
    path('price_history/<int:id>', views.GetPriceHistory.as_view()),
]
