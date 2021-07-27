from django.urls import path
from dds.activity import views


urlpatterns = [
    path('<int:page>/', views.GetActivityView.as_view()),
    path('topusers/<int:days>/', views.GetBestDealView.as_view())
]
