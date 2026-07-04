from django.core.exceptions import ValidationError
from django.test import TestCase
from accounts.models import User
from tenants.models import Tenant


class UserModelTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name='Sage Nine', slug='sage-nine')

    def test_platform_admin_has_no_tenant(self):
        user = User.objects.create_user(email='admin@example.com', password='test', role=User.Role.PLATFORM_ADMIN)
        self.assertTrue(user.is_staff)
        self.assertIsNone(user.tenant)

    def test_tenant_admin_requires_tenant(self):
        user = User(email='ta@example.com', role=User.Role.TENANT_ADMIN)
        with self.assertRaises(ValidationError):
            user.full_clean()

    def test_platform_admin_cannot_have_tenant(self):
        user = User(email='pa@example.com', role=User.Role.PLATFORM_ADMIN, tenant=self.tenant)
        with self.assertRaises(ValidationError):
            user.full_clean()
