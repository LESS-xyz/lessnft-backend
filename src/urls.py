from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from rest_framework import permissions

from django.contrib import admin
from django.urls import path
from django.urls import include
from django.conf.urls.static import static

from src.settings import MEDIA_URL, MEDIA_ROOT, STATIC_ROOT, STATIC_URL
from src.settings import config


schema_view = get_schema_view(
    openapi.Info(
        title=config.TITLE,
        default_version="v1",
        description=config.DESCRIPTION,
    ),
    public=True,
    permission_classes=(permissions.AllowAny,),
)

urlpatterns = [
    path("django-admin/", admin.site.urls),
    path(
        "api/v1/swagger/",
        schema_view.with_ui("swagger", cache_timeout=0),
        name="schema-swagger-ui",
    ),
    path("api/v1/account/", include("src.accounts.urls")),
    path("api/v1/rates/", include("src.rates.urls")),
    path("api/v1/store/", include("src.store.urls")),
    path("api/v1/activity/", include("src.activity.urls")),
    path("api/v1/networks/", include("src.networks.urls")),
]

urlpatterns += static(MEDIA_URL, document_root=MEDIA_ROOT)
urlpatterns += static(STATIC_URL, document_root=STATIC_ROOT)
