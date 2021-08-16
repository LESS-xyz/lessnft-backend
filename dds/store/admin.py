from django.contrib import admin
from django.db import models
from django.forms import CheckboxSelectMultiple
from dds.store.models import Token, Collection, Tags, Ownership
from django.utils.safestring import mark_safe

class TokenInline(admin.TabularInline):
    model = Token
    readonly_fields = ('id',)
    extra = 0



class TokenAdmin(admin.ModelAdmin):
    model = Token
    readonly_fields = ('id', 'image_preview')
    formfield_overrides = {
        models.ManyToManyField: {'widget': CheckboxSelectMultiple},
    }

    def image_preview(self, obj):
        # ex. the name of column is "image"
        if obj.ipfs:
            return mark_safe(
                '<img src="{0}" width="400" height="400" style="object-fit:contain" />'.format(obj.media))
        else:
            return '(No image)'

    image_preview.short_description = 'Preview'
    list_display = ('name', 'collection', 'standart', 'is_favorite')
    list_editable = ('is_favorite', )
    list_filter = ('standart', 'is_favorite')
    search_fields = ['name', 'collections']


class CollectionAdmin(admin.ModelAdmin):
    model = Collection
    inlines = (TokenInline,)
    readonly_fields = ('id',)
    list_display = ('name', 'address', 'standart', 'creator')
    list_filter = ('standart',)
    search_fields = ['creator', 'name']


class OwnershipAdmin(admin.ModelAdmin):
    model = Ownership
    list_display = ('token', 'owner', 'quantity')


admin.site.register(Tags)
admin.site.register(Ownership, OwnershipAdmin)
admin.site.register(Token, TokenAdmin)
admin.site.register(Collection, CollectionAdmin)
