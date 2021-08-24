from django.urls import path
from dds.activity import views


urlpatterns = [
    path('', views.ActivityView.as_view()),
    path('<str:address>/', views.UserActivityView.as_view()),
    path('<str:address>/following/', views.FollowingActivityView.as_view()),
    path('notification/', views.NotificationActivityView.as_view()),
    path('topusers/<int:days>/', views.GetBestDealView.as_view())
]
