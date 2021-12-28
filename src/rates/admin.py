from django.contrib import admin

from src.rates.models import UsdRate


class UsdRateAdmin(admin.ModelAdmin):
    model = UsdRate
    list_display = ("name", "symbol", "rate", "coin_node")
    list_filter = ("coin_node", "network")


admin.site.register(UsdRate, UsdRateAdmin)
