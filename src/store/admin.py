from django import forms
from django.contrib import admin
from django.contrib.sites.models import Site
from django.db import models
from django.forms import CheckboxSelectMultiple, ModelForm
from django.utils.safestring import mark_safe
from django_admin_inline_paginator.admin import TabularInlinePaginated
from django_celery_beat.models import (
    ClockedSchedule,
    CrontabSchedule,
    IntervalSchedule,
    PeriodicTask,
    SolarSchedule,
)

from src.store.models import Bid, Collection, NotableDrop, Ownership, Tags, Token
from src.store.services.ipfs import send_to_ipfs
from src.utilities import get_media_from_ipfs


class TagForm(forms.ModelForm):
    set_icon = forms.FileField(required=False)
    set_banner = forms.FileField(required=False)

    def save(self, commit=True):
        set_icon = self.cleaned_data.get("set_icon", None)
        set_banner = self.cleaned_data.get("set_banner", None)
        if set_icon:
            icon = send_to_ipfs(set_icon)
            self.instance.icon = icon
        if set_banner:
            banner = send_to_ipfs(set_banner)
            self.instance.banner = banner
        return super(TagForm, self).save(commit=commit)

    class Meta:
        model = Tags
        fields = "__all__"


class TagAdmin(admin.ModelAdmin):
    form = TagForm
    list_display = ("name", "icon")
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "name",
                    "set_icon",
                    "set_banner",
                    "icon",
                    "banner",
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


class TokenForm(forms.ModelForm):
    def clean(self):
        data = self.cleaned_data
        if not data.get("deleted") and data.get("collection").deleted:
            raise forms.ValidationError("Can't restore token in deleted collection.")
        return self.cleaned_data


class TokenAdmin(admin.ModelAdmin):
    model = Token
    form = TokenForm
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
    list_display = (
        "name",
        "collection",
        "status",
        "standart",
        "get_network",
        "is_favorite",
        "deleted",
    )
    list_editable = ("is_favorite",)
    list_filter = ("is_favorite", TokenStandartFilter, "status", "deleted")
    search_fields = [
        "name",
    ]

    def get_network(self, obj):
        return obj.collection.network.name

    get_network.short_description = "Network"
    get_network.admin_order_field = "collection__network__name"

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class CollectionForm(ModelForm):
    class Meta:
        models = Collection
        fields = "__all__"

    def clean(self):
        data = self.cleaned_data
        already_exists = (
            Collection.objects.network(data["network"])
            .filter(is_default=True, standart=data["standart"])
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
    list_display = ("name", "address", "standart", "creator", "get_network", "deleted")
    list_filter = ("standart", "deleted")
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

    def has_delete_permission(self, request, obj=None):
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


class NotableDropForm(forms.ModelForm):
    image_file = forms.ImageField(required=False)

    def save(self, commit=True):
        image_file = self.cleaned_data.get("image_file", None)
        if image_file:
            image = send_to_ipfs(image_file)
            self.instance.image = get_media_from_ipfs(image)
        return super(NotableDropForm, self).save(commit=commit)

    def clean(self):
        data = self.cleaned_data
        drops_count = NotableDrop.objects.count()
        current_drop = NotableDrop.objects.filter(collection=data["collection"]).first()
        if drops_count >= 3 and not self.instance.id:
            raise forms.ValidationError("There can be only three notable drops at once")
        if current_drop and (
            not self.instance.id or current_drop.id != self.instance.id
        ):
            raise forms.ValidationError(
                "You can not assert two notable drops for one collection"
            )
        return self.cleaned_data

    class Meta:
        model = NotableDrop
        fields = "__all__"


class NotableDropAdmin(admin.ModelAdmin):
    form = NotableDropForm
    list_display = ("collection",)
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "image_file",
                    "image",
                    "description",
                    "collection",
                    "background_color",
                ),
            },
        ),
    )


admin.site.register(Tags, TagAdmin)
admin.site.register(Ownership, OwnershipAdmin)
admin.site.register(Token, TokenAdmin)
admin.site.register(Bid, BidAdmin)
admin.site.register(Collection, CollectionAdmin)
admin.site.register(NotableDrop, NotableDropAdmin)

admin.site.unregister(SolarSchedule)
admin.site.unregister(ClockedSchedule)
# admin.site.unregister(PeriodicTask)
# admin.site.unregister(IntervalSchedule)
admin.site.unregister(CrontabSchedule)

admin.site.unregister(Site)
