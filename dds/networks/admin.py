from django.contrib import admin

from dds.networks.models import Network


class NetworkAdmin(admin.ModelAdmin):
    fields = (
        "name",
        "native_symbol",
        "endpoint",
        "needs_middleware",
        "fabric721_address",
        "fabric1155_address",
        "exchange_address",
        "network_type"
    )


admin.site.register(Network, NetworkAdmin)
