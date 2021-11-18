from django.contrib import admin
from .models import UserAction, TokenHistory, BidsHistory, CollectionStat


class UserActionAdmin(admin.ModelAdmin):
    model = UserAction
    readonly_fields = ('id',)
    list_display = ('user', 'method', 'date')
    list_filter = ('method',)
    ordering = ('-date',)


class TokenHistoryAdmin(admin.ModelAdmin):
    model = TokenHistory
    list_display = ('token', 'amount', 'old_owner', 'method', 'date', 'price')
    list_filter = ('method',)
    ordering = ('-date',)

class BidsHistoryAdmin(admin.ModelAdmin):
    model = BidsHistory
    list_display = ('token', 'user', 'price', 'date')
    ordering = ('-date',)


admin.site.register(UserAction, UserActionAdmin)
admin.site.register(TokenHistory, TokenHistoryAdmin)
admin.site.register(BidsHistory, BidsHistoryAdmin)
admin.site.register(CollectionStat)
