from django.urls import path
from dds.activity import views


urlpatterns = [
    path('', views.ActivityView.as_view()),
    path('<str:address>/', views.UserActivityView.as_view()),
    path('topusers/<int:days>/', views.GetBestDealView.as_view())
]
