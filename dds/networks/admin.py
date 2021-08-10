from django.contrib import admin

from dds.networks.models import Network


class NetworkAdmin(admin.ModelAdmin):
    fields = (
        'name', 
        'erc721_main_address', 
        'erc1155_main_address', 
        'erc721_fabric_address', 
        'erc1155_fabric_address', 
        'exchange_address', 
        'weth_address', 
        'endpoint', 
        'needs_middleware',
    )


admin.site.register(Network, NetworkAdmin)
