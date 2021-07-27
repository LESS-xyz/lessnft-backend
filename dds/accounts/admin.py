from django.contrib import admin
from django.contrib.auth.models import Group
from dds.accounts.models import AdvUser, VerificationForm, MasterUser
from allauth.socialaccount.models import SocialToken, SocialAccount, SocialApp
from allauth.account.models import EmailAddress

class VerificationInline(admin.StackedInline):
    model = VerificationForm
    readonly_fields = ('id',)
    extra = 0

class AdvUserAdmin(admin.ModelAdmin):
    model = AdvUser
    inlines = (VerificationInline,)
    readonly_fields = ('id',)
    list_display = ('username', 'display_name', 'is_verificated')
    exclude = ('is_staff', 'groups', 'first_name', 'last_name', 'is_superuser', 'user_permissions', 'email')

class MasterUserAdmin(admin.ModelAdmin):
    model = MasterUser
    list_display = ('address', 'commission')


admin.site.register(MasterUser, MasterUserAdmin)
admin.site.register(AdvUser, AdvUserAdmin)
admin.site.unregister(Group)
admin.site.unregister(SocialToken)
admin.site.unregister(SocialAccount)
admin.site.unregister(SocialApp)
admin.site.unregister(EmailAddress)
