from django import forms
from django.contrib import admin
from django.contrib.auth.models import Group
from dds.accounts.models import AdvUser, VerificationForm, MasterUser, DefaultAvatar
from allauth.socialaccount.models import SocialToken, SocialAccount, SocialApp
from allauth.account.models import EmailAddress

from dds.store.services.ipfs import send_to_ipfs


class DefaultAvatarForm(forms.ModelForm):
    avatar = forms.ImageField()

    def save(self, commit=True):
        avatar = self.cleaned_data.get('avatar', None)
        image = send_to_ipfs(avatar)
        self.instance.image = image
        return super(DefaultAvatarForm, self).save(commit=commit)

    class Meta:
        model = DefaultAvatar
        fields = "__all__"


class DefaultAvatarAdmin(admin.ModelAdmin):
    form = DefaultAvatarForm
    list_display = ('image', )
    fieldsets = (
        (None, {
            'fields': ('avatar', 'image', ),
        }),
    )


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
admin.site.register(DefaultAvatar, DefaultAvatarAdmin)
admin.site.unregister(Group)
admin.site.unregister(SocialToken)
admin.site.unregister(SocialAccount)
admin.site.unregister(SocialApp)
admin.site.unregister(EmailAddress)
