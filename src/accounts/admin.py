from allauth.account.models import EmailAddress
from allauth.socialaccount.models import SocialAccount, SocialApp, SocialToken
from django import forms
from django.contrib import admin
from django.contrib.auth.models import Group
from rest_framework.authtoken.models import TokenProxy

from src.accounts.models import AdvUser, DefaultAvatar, MasterUser, VerificationForm
from src.store.services.ipfs import send_to_ipfs


class DefaultAvatarForm(forms.ModelForm):
    avatar = forms.ImageField()

    def save(self, commit=True):
        avatar = self.cleaned_data.get("avatar", None)
        image = send_to_ipfs(avatar)
        self.instance.image = image
        return super(DefaultAvatarForm, self).save(commit=commit)

    class Meta:
        model = DefaultAvatar
        fields = "__all__"


class DefaultAvatarAdmin(admin.ModelAdmin):
    form = DefaultAvatarForm
    list_display = ("image",)
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "avatar",
                    "image",
                ),
            },
        ),
    )


class VerificationInline(admin.StackedInline):
    model = VerificationForm
    readonly_fields = ("id",)
    extra = 0


class AdvUserAdmin(admin.ModelAdmin):
    model = AdvUser
    inlines = (VerificationInline,)
    readonly_fields = ("id", "date_joined", "last_login")
    list_display = ("username", "display_name", "is_verificated")
    exclude = (
        "is_superuser",
        "first_name",
        "is_staff",
        "groups",
        "last_name",
        "user_permissions",
        "email",
        "password",
    )


class MasterUserAdmin(admin.ModelAdmin):
    model = MasterUser
    list_display = ("address", "commission", "network")
    readonly_fields = ("network",)

    def has_delete_permission(self, request, obj=None):
        path = request.path
        if path.startswith("/django-admin/accounts/masteruser/"):
            return False
        return True

    def has_add_permission(self, request):
        return None


admin.site.register(MasterUser, MasterUserAdmin)
admin.site.register(AdvUser, AdvUserAdmin)
admin.site.register(DefaultAvatar, DefaultAvatarAdmin)
admin.site.unregister(Group)
admin.site.unregister(SocialToken)
admin.site.unregister(SocialAccount)
admin.site.unregister(SocialApp)
admin.site.unregister(EmailAddress)
admin.site.unregister(TokenProxy)
