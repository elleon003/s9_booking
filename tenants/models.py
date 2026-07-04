from django.db import models
from django.db.models import QuerySet


class Tenant(models.Model):
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True, db_index=True)
    is_active = models.BooleanField(default=True)
    branding = models.JSONField(default=dict, blank=True)
    config = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class TenantQuerySet(QuerySet):
    def for_tenant(self, tenant):
        return self.filter(tenant=tenant)

    def for_request(self, request):
        tenant = getattr(request, 'tenant', None)
        if tenant is None:
            return self.none()
        return self.for_tenant(tenant)


class TenantManager(models.Manager.from_queryset(TenantQuerySet)):
    pass


class TenantMixin(models.Model):
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        db_index=True,
    )
    objects = TenantManager()

    class Meta:
        abstract = True
