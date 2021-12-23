from src.store.services.ipfs import send_to_ipfs
from django.contrib import admin

from src.networks.models import Network
from django import forms


class NetworkIconForm(forms.ModelForm):
    set_icon = forms.FileField(required=False)

    def save(self, commit=True):
        set_icon = self.cleaned_data.get("set_icon", None)
        if set_icon:
            icon = send_to_ipfs(set_icon)
            self.instance.icon = icon
        return super(NetworkIconForm, self).save(commit=commit)

    class Meta:
        model = Network
        fields = "__all__"


class NetworkAdmin(admin.ModelAdmin):
    form = NetworkIconForm
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "name",
                    "set_icon",
                    "native_symbol",
                    "endpoint",
                    "needs_middleware",
                    "fabric721_address",
                    "fabric1155_address",
                    "exchange_address",
                    "network_type",
                ),
            },
        ),
    )


admin.site.register(Network, NetworkAdmin)
