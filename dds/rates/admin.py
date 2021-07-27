from django.contrib import admin
from dds.rates.models import UsdRate


class UsdRateAdmin(admin.ModelAdmin):
    readonly_fields = ('id',)
    list_display = ('currency', 'rate', 'updated_at')

admin.site.register(UsdRate, UsdRateAdmin)
