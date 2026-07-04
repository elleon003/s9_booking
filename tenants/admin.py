from django.contrib import admin
from unfold.admin import ModelAdmin

from tenants.models import Tenant


@admin.register(Tenant)
class TenantAdmin(ModelAdmin):
    list_display = ('name', 'slug', 'is_active', 'created_at')
    search_fields = ('name', 'slug')
    list_filter = ('is_active',)
    fieldsets = (
        (None, {'fields': ('name', 'slug', 'is_active')}),
        ('Branding', {'fields': ('branding',)}),
        ('Configuration', {'fields': ('config',)}),
    )
