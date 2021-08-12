from django.contrib import admin
from dds.rates.models import UsdRate


class UsdRateAdmin(admin.ModelAdmin):
    readonly_fields = ('id',)
    list_display = (
        'rate', 
        'coin_node', 
        'image', 
        'name', 
        'symbol', 
        'updated_at',
    )

admin.site.register(UsdRate, UsdRateAdmin)
