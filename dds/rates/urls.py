from django.urls import path
from dds.rates.views import RateRequest

urlpatterns = [
    path('', RateRequest.as_view()),
]
