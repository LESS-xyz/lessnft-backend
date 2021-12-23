from src.store.services.ipfs import send_to_ipfs
from src.store.models import (
    Bid,
    Collection,
    Ownership,
    Tags,
    Token,
)
from django import forms
from django.contrib import admin
from django.db import models
from django.forms import CheckboxSelectMultiple, ModelForm
from django.utils.safestring import mark_safe
from django_celery_beat.models import (
    ClockedSchedule,
    CrontabSchedule,
    SolarSchedule,
    PeriodicTask,
    IntervalSchedule,
)
from django.contrib.sites.models import Site
from django_admin_inline_paginator.admin import TabularInlinePaginated


class TagIconForm(forms.ModelForm):
    set_icon = forms.FileField(required=False)

    def save(self, commit=True):
        set_icon = self.cleaned_data.get("set_icon", None)
        if set_icon:
            icon = send_to_ipfs(set_icon)
            self.instance.icon = icon
        return super(TagIconForm, self).save(commit=commit)

    class Meta:
        model = Tags
        fields = "__all__"


class TagAdmin(admin.ModelAdmin):
    form = TagIconForm
    list_display = ("name", "icon")
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "name",
                    "set_icon",
                    "icon",
                ),
            },
        ),
    )


class TokenStandartFilter(admin.SimpleListFilter):
    title = "token standart"
    parameter_name = "token_standart"

    def lookups(self, request, model_admin):
        return (
            ("ERC721", "ERC721"),
            ("ERC1155", "ERC1155"),
        )

    def queryset(self, request, queryset):
        value = self.value()
        if value == "ERC721":
            return queryset.filter(collection__standart="ERC721")
        elif value == "ERC1155":
            return queryset.filter(collection__standart="ERC1155")
        return queryset


class TokenInline(TabularInlinePaginated):
    model = Token
    readonly_fields = ("id",)
    extra = 0
    per_page = 25


class BidAdmin(admin.ModelAdmin):
    model = Bid
    list_display = ("token", "user")

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request):
        return False


class TokenAdmin(admin.ModelAdmin):
    model = Token
    readonly_fields = ("id", "image_preview", "updated_at")
    formfield_overrides = {
        models.ManyToManyField: {"widget": CheckboxSelectMultiple},
    }

    def image_preview(self, obj):
        # ex. the name of column is "image"
        if obj.ipfs:
            return mark_safe(
                '<img src="{0}" width="400" height="400" style="object-fit:contain" />'.format(
                    obj.media
                )
            )
        else:
            return "(No image)"

    image_preview.short_description = "Preview"
    list_display = ("name", "collection", "standart", "is_favorite", "get_network")
    list_editable = ("is_favorite",)
    list_filter = ("is_favorite", TokenStandartFilter)
    search_fields = [
        "name",
    ]

    def get_network(self, obj):
        return obj.collection.network.name

    get_network.short_description = "Network"
    get_network.admin_order_field = "collection__network__name"

    def has_add_permission(self, request):
        return False


class CollectionForm(ModelForm):
    class Meta:
        models = Collection
        fields = "__all__"

    def clean(self):
        data = self.cleaned_data
        already_exists = (
            Collection.objects.network(data["network"])
            .filter(is_default=True)
            .exclude(name=data["name"])
        )
        if data["is_default"] and already_exists.exists():
            raise forms.ValidationError(
                f"There can be only one default {data['standart']} collection for network {data['network']}"
            )
        return self.cleaned_data


class CollectionAdmin(admin.ModelAdmin):
    model = Collection
    inlines = (TokenInline,)
    readonly_fields = ("id",)
    list_display = ("name", "address", "standart", "creator", "get_network")
    list_filter = ("standart",)
    search_fields = [
        "name",
    ]
    form = CollectionForm

    def get_network(self, obj):
        return obj.network.name

    get_network.short_description = "Network"
    get_network.admin_order_field = "collection__network__name"

    def has_add_permission(self, request):
        return False


class OwnershipAdmin(admin.ModelAdmin):
    model = Ownership
    list_display = ("token", "owner", "quantity")

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request):
        return False


admin.site.register(Tags, TagAdmin)
admin.site.register(Ownership, OwnershipAdmin)
admin.site.register(Token, TokenAdmin)
admin.site.register(Bid, BidAdmin)
admin.site.register(Collection, CollectionAdmin)

admin.site.unregister(SolarSchedule)
admin.site.unregister(ClockedSchedule)
admin.site.unregister(PeriodicTask)
admin.site.unregister(IntervalSchedule)
admin.site.unregister(CrontabSchedule)

admin.site.unregister(Site)
