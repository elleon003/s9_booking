from django.conf import settings
from django.http import Http404

from tenants.models import Tenant


class TenantMiddleware:
    SKIP_PREFIXES = ('/admin/', '/accounts/', '/two_factor/', '/static/', '/media/')

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.tenant = self.resolve_tenant(request)
        return self.get_response(request)

    def resolve_tenant(self, request):
        path = request.path_info
        if path.startswith(self.SKIP_PREFIXES):
            return None

        # Path-based resolution: /t/<slug>/
        if path.startswith('/t/'):
            parts = path.split('/')
            if len(parts) >= 3 and parts[2]:
                slug = parts[2]
                return self.get_active_tenant(slug)

        # Subdomain-based resolution
        host = request.get_host().split(':')[0]
        base_host = getattr(settings, 'BASE_HOST', host)
        if host and host != base_host and host.endswith(f'.{base_host}'):
            slug = host[:-(len(base_host) + 1)]
            return self.get_active_tenant(slug)

        return None

    def get_active_tenant(self, slug):
        try:
            return Tenant.objects.get(slug=slug, is_active=True)
        except Tenant.DoesNotExist:
            return None
