from django.contrib import admin
from django.core.exceptions import ValidationError
from django.forms import ModelForm
from unfold.admin import ModelAdmin

from accounts.models import User


class UserAdminForm(ModelForm):
    class Meta:
        model = User
        fields = '__all__'

    def clean(self):
        cleaned_data = super().clean()
        role = cleaned_data.get('role')
        tenant = cleaned_data.get('tenant')
        if role == User.Role.PLATFORM_ADMIN and tenant is not None:
            raise ValidationError('Platform admins cannot be assigned to a tenant.')
        if role in (User.Role.TENANT_ADMIN, User.Role.TENANT_STAFF) and tenant is None:
            raise ValidationError('Tenant admins and staff must be assigned to a tenant.')
        return cleaned_data


@admin.register(User)
class UserAdmin(ModelAdmin):
    form = UserAdminForm
    list_display = ('email', 'role', 'tenant', 'is_active', 'date_joined')
    list_filter = ('role', 'is_active', 'tenant')
    search_fields = ('email', 'first_name', 'last_name')
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Profile', {'fields': ('first_name', 'last_name', 'role', 'tenant')}),
        ('Status', {'fields': ('is_active', 'is_staff', 'is_superuser')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )
    readonly_fields = ('is_staff',)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.role == User.Role.PLATFORM_ADMIN:
            return qs
        return qs.filter(tenant=request.user.tenant)

    def has_module_permission(self, request):
        return request.user.is_authenticated and request.user.role == User.Role.PLATFORM_ADMIN

    def has_view_permission(self, request, obj=None):
        return request.user.is_authenticated and request.user.role == User.Role.PLATFORM_ADMIN

    def has_add_permission(self, request):
        return request.user.is_authenticated and request.user.role == User.Role.PLATFORM_ADMIN

    def has_change_permission(self, request, obj=None):
        return request.user.is_authenticated and request.user.role == User.Role.PLATFORM_ADMIN

    def has_delete_permission(self, request, obj=None):
        return request.user.is_authenticated and request.user.role == User.Role.PLATFORM_ADMIN
