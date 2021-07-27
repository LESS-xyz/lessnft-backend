from django.contrib import admin
from .models import UserAction, TokenHistory, BidsHistory


class UserActionAdmin(admin.ModelAdmin):
    model = UserAction
    readonly_fields = ('id',)
    list_display = ('user', 'method', 'date')
    list_filter = ('method',)
    search_fields = ['user']
    ordering = ('-date',)


class TokenHistoryAdmin(admin.ModelAdmin):
    model = TokenHistory
    list_display = ('token', 'method', 'date')
    list_filter = ('method',)
    search_fields = ['user']
    ordering = ('-date',)

class BidsHistoryAdmin(admin.ModelAdmin):
    model = BidsHistory
    list_display = ('token', 'user', 'price', 'date')
    ordering = ('-date',)


admin.site.register(UserAction, UserActionAdmin)
admin.site.register(TokenHistory, TokenHistoryAdmin)
admin.site.register(BidsHistory, BidsHistoryAdmin)
