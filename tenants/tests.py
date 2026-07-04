from django.test import RequestFactory, TestCase, override_settings
from tenants.middleware import TenantMiddleware
from tenants.models import Tenant


@override_settings(ALLOWED_HOSTS=['testserver', 's9booking.local', '.s9booking.local'])
class TenantMiddlewareTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.tenant = Tenant.objects.create(name='Sage Nine', slug='sage-nine')
        self.middleware = TenantMiddleware(lambda request: getattr(request, 'tenant', None))

    def test_path_resolution(self):
        request = self.factory.get('/t/sage-nine/')
        self.middleware(request)
        self.assertEqual(request.tenant, self.tenant)

    def test_subdomain_resolution(self):
        request = self.factory.get('/', HTTP_HOST='sage-nine.s9booking.local')
        self.middleware(request)
        self.assertEqual(request.tenant, self.tenant)

    def test_unknown_tenant_is_none(self):
        request = self.factory.get('/t/unknown/')
        self.middleware(request)
        self.assertIsNone(request.tenant)

    def test_admin_paths_skip_resolution(self):
        request = self.factory.get('/admin/login/', HTTP_HOST='sage-nine.s9booking.local')
        self.middleware(request)
        self.assertIsNone(request.tenant)
