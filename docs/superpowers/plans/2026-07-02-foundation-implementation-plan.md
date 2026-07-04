# Foundation Milestone Implementation Plan

> **Note:** Tasks related to `templates/base.html`, `templates/home.html`, inline CSS, and `.env` setup are superseded by `docs/superpowers/plans/2026-07-03-tailwind-ui-refactor-implementation-plan.md`.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Foundation milestone: custom auth with roles, multi-tenant models and middleware, 2FA-enforced Django admin for platform admins only, and Sage Nine Creative branding in Unfold.

**Architecture:** Two local Django apps (`accounts`, `tenants`) split auth and tenancy concerns. A custom `User` model uses email as the username and carries a role plus optional tenant FK. A `TenantMiddleware` resolves `request.tenant` from URL path or subdomain. `django-two-factor-auth` enforces OTP for `/admin/` via `AdminSiteOTPRequired`. Unfold admin is themed with the Sage Nine Creative palette and fonts.

**Tech Stack:** Django 6.0, django-unfold, django-tailwind v4, django-two-factor-auth, environs, SQLite (dev).

## Global Constraints

- Django virtualenv lives at `.venv/`; use `.venv/bin/python manage.py <cmd>`.
- `unfold` and its contrib apps must stay **before** `django.contrib.admin` in `INSTALLED_APPS`.
- `django_otp.middleware.OTPMiddleware` must be placed after `AuthenticationMiddleware`.
- `SECRET_KEY`, `DEBUG`, and `ALLOWED_HOSTS` are required in `.env`.
- `staticfiles.W004` warning is expected and must not be "fixed" by removing the setting.
- No test suite/linter/typechecker is configured; verification is manual via `manage.py check`, `manage.py migrate`, and targeted Django TestCase checks.
- Brand colors: Deep Sage `#50665A`, Charcoal `#333333`, Terracotta `#CC7755`, Pale Cream `#F8F8F0`. Fonts: DM Sans and Lora.

---

## File Structure

| File | Responsibility |
|------|--------------|
| `accounts/models.py` | Custom `User` model with roles and tenant FK |
| `accounts/admin.py` | Unfold `UserAdmin`; enforces role/tenant constraints and admin access |
| `accounts/forms.py` | User change form used by admin |
| `accounts/apps.py` | App config for `accounts` |
| `tenants/models.py` | `Tenant`, `TenantMixin`, `TenantQuerySet` |
| `tenants/middleware.py` | `TenantMiddleware` |
| `tenants/admin.py` | Unfold `TenantAdmin` |
| `tenants/apps.py` | App config for `tenants` |
| `config/settings/base.py` | Add apps, middleware, 2FA URLs, Unfold brand config, `BASE_HOST` |
| `config/settings/dev.py` | Dev email backend, `INTERNAL_IPS` for browser reload |
| `config/urls.py` | OTP-required admin, two_factor URLs, public `home` view |
| `config/views.py` | Minimal `home` view |
| `templates/base.html` | Base template loading DM Sans + Lora, brand colors as CSS vars |
| `templates/home.html` | Landing placeholder |
| `requirements.txt` | Add `django-two-factor-auth` |
| `.env` | Add `BASE_HOST` and `DEFAULT_FROM_EMAIL` |
| `accounts/tests.py` | User model validation tests |
| `tenants/tests.py` | Tenant middleware resolution tests |

---

### Task 1: Scaffold `accounts` and `tenants` apps

**Files:**
- Create: `accounts/__init__.py`, `accounts/apps.py`
- Create: `tenants/__init__.py`, `tenants/apps.py`
- Modify: `config/settings/base.py` (register apps)

**Interfaces:**
- Produces: `accounts` and `tenants` registered in `INSTALLED_APPS`.

- [ ] **Step 1: Create `accounts/apps.py`**

```python
from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'accounts'
```

- [ ] **Step 2: Create `accounts/__init__.py`**

```python
default_app_config = 'accounts.apps.AccountsConfig'
```

- [ ] **Step 3: Create `tenants/apps.py`**

```python
from django.apps import AppConfig


class TenantsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'tenants'
```

- [ ] **Step 4: Create `tenants/__init__.py`**

```python
default_app_config = 'tenants.apps.TenantsConfig'
```

- [ ] **Step 5: Register apps in `config/settings/base.py`**

Add `'accounts'` and `'tenants'` under `# Local apps` after `theme`:

```python
    # Local apps
    'tailwind',
    'theme',
    'accounts',
    'tenants',
```

- [ ] **Step 6: Run `check` to verify app registration**

Run: `.venv/bin/python manage.py check`
Expected: passes with only `staticfiles.W004` warning.

---

### Task 2: Build `tenants` models

**Files:**
- Create: `tenants/models.py`
- Modify: `config/settings/base.py` (no changes yet)

**Interfaces:**
- Produces: `Tenant`, `TenantMixin`, `TenantQuerySet`, `TenantManager`.

- [ ] **Step 1: Write the failing test in `tenants/tests.py`**

Create `tenants/tests.py`:

```python
from django.test import TestCase
from tenants.models import Tenant


class TenantModelTests(TestCase):
    def test_tenant_creation(self):
        tenant = Tenant.objects.create(name='Sage Nine Creative', slug='sage-nine')
        self.assertEqual(tenant.slug, 'sage-nine')
        self.assertTrue(tenant.is_active)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python manage.py test tenants.tests.TenantModelTests.test_tenant_creation -v 2`
Expected: FAIL — `ModuleNotFoundError: No module named 'tenants.tests'` or model not defined.

- [ ] **Step 3: Implement `tenants/models.py`**

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python manage.py test tenants.tests.TenantModelTests.test_tenant_creation -v 2`
Expected: PASS.

- [ ] **Step 5: Make migrations**

Run: `.venv/bin/python manage.py makemigrations tenants`
Expected: creates `tenants/migrations/0001_initial.py` with `Tenant` model.

---

### Task 3: Build `accounts.User` model

**Files:**
- Create: `accounts/models.py`
- Modify: `config/settings/base.py` (set `AUTH_USER_MODEL`)

**Interfaces:**
- Produces: `accounts.User` with `role`, `tenant`, email-as-username.

- [ ] **Step 1: Write failing tests in `accounts/tests.py`**

Create `accounts/tests.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python manage.py test accounts.tests -v 2`
Expected: FAIL — `User` model does not exist.

- [ ] **Step 3: Implement `accounts/models.py`**

```python
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models


class User(AbstractUser):
    class Role(models.TextChoices):
        PLATFORM_ADMIN = 'platform_admin', 'Platform Admin'
        TENANT_ADMIN = 'tenant_admin', 'Tenant Admin'
        TENANT_STAFF = 'tenant_staff', 'Tenant Staff'

    username = None
    email = models.EmailField(unique=True)
    role = models.CharField(max_length=20, choices=Role.choices)
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    class Meta:
        ordering = ['email']

    def clean(self):
        super().clean()
        if self.role == self.Role.PLATFORM_ADMIN and self.tenant is not None:
            raise ValidationError('Platform admins cannot be assigned to a tenant.')
        if self.role in (self.Role.TENANT_ADMIN, self.Role.TENANT_STAFF) and self.tenant is None:
            raise ValidationError('Tenant admins and staff must be assigned to a tenant.')

    def save(self, *args, **kwargs):
        self.is_staff = self.role == self.Role.PLATFORM_ADMIN
        super().save(*args, **kwargs)
```

- [ ] **Step 4: Set `AUTH_USER_MODEL` in `config/settings/base.py`**

Add near the bottom (before internationalization is fine):

```python
AUTH_USER_MODEL = 'accounts.User'
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/python manage.py test accounts.tests -v 2`
Expected: PASS.

- [ ] **Step 6: Make migrations**

Run: `.venv/bin/python manage.py makemigrations accounts`
Expected: creates `accounts/migrations/0001_initial.py` with `User` model.

---

### Task 4: Implement `TenantMiddleware`

**Files:**
- Create: `tenants/middleware.py`
- Modify: `config/settings/base.py` (add middleware, add `BASE_HOST`)
- Modify: `.env` (add `BASE_HOST`)
- Create: `tenants/tests.py` (add middleware tests)

**Interfaces:**
- Consumes: `Tenant.objects.get(slug=..., is_active=True)`.
- Produces: `request.tenant` (`Tenant` or `None`).

- [ ] **Step 1: Add `BASE_HOST` to `.env`**

```text
BASE_HOST=s9booking.local
```

- [ ] **Step 2: Read `BASE_HOST` in `config/settings/base.py`**

Add after `ALLOWED_HOSTS` line:

```python
BASE_HOST = env.str('BASE_HOST', default='s9booking.local')
```

- [ ] **Step 3: Write failing middleware tests in `tenants/tests.py`**

Append to `tenants/tests.py`:

```python
from django.test import RequestFactory, TestCase, override_settings
from tenants.middleware import TenantMiddleware
from tenants.models import Tenant


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
        self.assertFalse(hasattr(request, 'tenant'))
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `.venv/bin/python manage.py test tenants.tests.TenantMiddlewareTests -v 2`
Expected: FAIL — `TenantMiddleware` not defined.

- [ ] **Step 5: Implement `tenants/middleware.py`**

```python
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
```

- [ ] **Step 6: Register middleware in `config/settings/base.py`**

Add after `AuthenticationMiddleware`:

```python
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django_otp.middleware.OTPMiddleware',
    'tenants.middleware.TenantMiddleware',
```

Note: `django_otp.middleware.OTPMiddleware` is added here too for the next task. If you prefer strict ordering, add it now; otherwise add it in Task 5.

- [ ] **Step 7: Run tests to verify they pass**

Run: `.venv/bin/python manage.py test tenants.tests.TenantMiddlewareTests -v 2`
Expected: PASS.

---

### Task 5: Integrate `django-two-factor-auth`

**Files:**
- Modify: `requirements.txt`
- Modify: `config/settings/base.py` (apps, middleware, login URLs)
- Modify: `config/urls.py` (OTP admin, two_factor URLs)
- Modify: `.env` (`DEFAULT_FROM_EMAIL`)
- Modify: `config/settings/dev.py` (email backend)

**Interfaces:**
- Produces: `/admin/` requires OTP; `/accounts/` includes two_factor views.

- [ ] **Step 1: Add package to `requirements.txt`**

```text
django-two-factor-auth~=1.17.0
```

- [ ] **Step 2: Install package**

Run: `.venv/bin/python -m pip install django-two-factor-auth~=1.17.0`
Expected: installs `django-two-factor-auth`, `django-otp`, `django-formtools`, etc.

- [ ] **Step 3: Add 2FA apps to `config/settings/base.py`**

Insert after `django.contrib.staticfiles` and before `tailwind`:

```python
    'django.contrib.staticfiles',

    # Two-factor authentication
    'django_otp',
    'django_otp.plugins.otp_static',
    'django_otp.plugins.otp_totp',
    'django_otp.plugins.otp_email',
    'two_factor',
    'two_factor.plugins.email',

    # Third-party apps
    'tailwind',
```

- [ ] **Step 4: Add OTP middleware in `config/settings/base.py`**

Ensure `MIDDLEWARE` contains:

```python
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django_otp.middleware.OTPMiddleware',
    'tenants.middleware.TenantMiddleware',
```

- [ ] **Step 5: Add login URLs and email settings in `config/settings/base.py`**

Add near the bottom:

```python
LOGIN_URL = 'two_factor:login'
LOGIN_REDIRECT_URL = 'admin:index'
DEFAULT_FROM_EMAIL = env.str('DEFAULT_FROM_EMAIL', default='dev@s9booking.local')
```

- [ ] **Step 6: Add `DEFAULT_FROM_EMAIL` and `BASE_HOST` to `.env`**

Ensure `.env` contains:

```text
SECRET_KEY=django-insecure-...
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1,::1,s9booking.local,*.s9booking.local
BASE_HOST=s9booking.local
DEFAULT_FROM_EMAIL=dev@s9booking.local
```

- [ ] **Step 7: Configure dev email backend in `config/settings/dev.py`**

Add:

```python
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
```

Also fix the browser reload issue noted in `AGENTS.md`:

```python
INTERNAL_IPS = ['127.0.0.1']
```

- [ ] **Step 8: Wire URLs in `config/urls.py`**

```python
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from two_factor.admin import AdminSiteOTPRequired

from config.views import home

admin.site.__class__ = AdminSiteOTPRequired

urlpatterns = [
    path('', home, name='home'),
    path('accounts/', include('two_factor.urls', namespace='two_factor')),
    path('admin/', admin.site.urls),
]

if settings.DEBUG:
    urlpatterns += [path('__reload__/', include('django_browser_reload.urls'))]
```

- [ ] **Step 9: Run migrations**

Run: `.venv/bin/python manage.py migrate`
Expected: applies 2FA tables, accounts, tenants.

- [ ] **Step 10: Run `check`**

Run: `.venv/bin/python manage.py check`
Expected: passes with only `staticfiles.W004` warning.

---

### Task 6: Build `config/views.py` and templates

**Files:**
- Create: `config/views.py`
- Create: `templates/base.html`
- Create: `templates/home.html`
- Modify: `config/settings/base.py` (template DIRS)

**Interfaces:**
- Consumes: `request.tenant`.
- Produces: rendered `home.html`.

- [ ] **Step 1: Create `templates/base.html`**

```html
{% load static %}
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{% block title %}S9 Booking{% endblock %}</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;700&family=Lora:wght@400;500;700&display=swap" rel="stylesheet">
  <style>
    :root {
      --deep-sage: #50665A;
      --charcoal: #333333;
      --terracotta: #CC7755;
      --pale-cream: #F8F8F0;
    }
    body {
      font-family: 'DM Sans', sans-serif;
      background-color: var(--pale-cream);
      color: var(--charcoal);
      margin: 0;
      padding: 2rem;
    }
    h1, h2, h3 {
      font-family: 'Lora', serif;
      color: var(--deep-sage);
    }
    a {
      color: var(--terracotta);
    }
  </style>
  {% block extra_head %}{% endblock %}
</head>
<body>
  {% block content %}{% endblock %}
</body>
</html>
```

- [ ] **Step 2: Create `templates/home.html`**

```html
{% extends "base.html" %}

{% block title %}{% if tenant %}{{ tenant.name }} Booking{% else %}S9 Booking{% endif %}{% endblock %}

{% block content %}
  {% if tenant %}
    <h1>Welcome to {{ tenant.name }}</h1>
    <p>Book your appointment with {{ tenant.name }}.</p>
  {% else %}
    <h1>Welcome to S9 Booking</h1>
    <p>Simple, trustworthy scheduling for service businesses and agencies.</p>
  {% endif %}
{% endblock %}
```

- [ ] **Step 3: Create `config/views.py`**

```python
from django.shortcuts import render


def home(request):
    return render(request, 'home.html', {'tenant': getattr(request, 'tenant', None)})
```

- [ ] **Step 4: Register templates directory in `config/settings/base.py`**

Update `TEMPLATES[0]['DIRS']`:

```python
            'DIRS': [BASE_DIR / 'templates'],
```

- [ ] **Step 5: Verify home page renders**

Run dev server or use test client:

```python
.venv/bin/python manage.py shell -c "
from django.test import Client
c = Client()
r = c.get('/', HTTP_HOST='127.0.0.1')
print(r.status_code, 'Welcome' in r.content.decode())
"
```
Expected: `200 True`.

---

### Task 7: Build Unfold admin for `User` and `Tenant`

**Files:**
- Modify: `accounts/admin.py`
- Modify: `tenants/admin.py`
- Modify: `config/settings/base.py` (`UNFOLD` brand config + sidebar)

**Interfaces:**
- Consumes: `User`, `Tenant` models.
- Produces: styled admin list/change views; only platform admins access admin.

- [ ] **Step 1: Create `accounts/forms.py`**

```python
from django.contrib.auth.forms import UserChangeForm
from accounts.models import User


class UserChangeForm(UserChangeForm):
    class Meta:
        model = User
        fields = ('email', 'first_name', 'last_name', 'role', 'tenant', 'is_active')
```

- [ ] **Step 2: Create `accounts/admin.py`**

```python
from django.contrib import admin
from django.core.exceptions import ValidationError
from django.forms import ModelForm
from unfold.admin import ModelAdmin

from accounts.forms import UserChangeForm
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
```

- [ ] **Step 3: Create `tenants/admin.py`**

```python
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
```

- [ ] **Step 4: Update `UNFOLD` brand config in `config/settings/base.py`**

Replace the existing `UNFOLD` dict (or update it) with:

```python
UNFOLD = {
    'SITE_TITLE': _('S9 Booking'),
    'SITE_HEADER': _('S9 Booking'),
    'SITE_SUBHEADER': _('Administration'),
    'SITE_URL': '/',
    'COLORS': {
        'primary': {
            '50': '#F4F6F5',
            '100': '#E3E8E5',
            '200': '#C7D1CB',
            '300': '#A5B5AC',
            '400': '#82948B',
            '500': '#50665A',
            '600': '#45584E',
            '700': '#3A4A41',
            '800': '#2F3B35',
            '900': '#242D29',
        },
        'secondary': {
            '50': '#F8F8F0',
            '100': '#F2F2E8',
            '200': '#E8E8DA',
            '300': '#D9D9C7',
            '400': '#C4C4AE',
            '500': '#333333',
            '600': '#2E2E2E',
            '700': '#292929',
            '800': '#242424',
            '900': '#1F1F1F',
        },
        'terracotta': {
            '50': '#FDF4F0',
            '100': '#FAE6DE',
            '200': '#F5CCBC',
            '300': '#EBAA93',
            '400': '#D99077',
            '500': '#CC7755',
            '600': '#B56849',
            '700': '#9E5A3E',
            '800': '#874C34',
            '900': '#703E2B',
        },
    },
    'SIDEBAR': {
        'show_search': True,
        'show_all_applications': True,
        'navigation': [
            {
                'title': _('Management'),
                'separator': True,
                'items': [
                    {
                        'title': _('Dashboard'),
                        'icon': 'dashboard',
                        'link': reverse_lazy('admin:index'),
                    },
                    {
                        'title': _('Users'),
                        'icon': 'people',
                        'link': reverse_lazy('admin:accounts_user_changelist'),
                    },
                    {
                        'title': _('Tenants'),
                        'icon': 'domain',
                        'link': reverse_lazy('admin:tenants_tenant_changelist'),
                    },
                ],
            },
        ],
    },
    'STYLES': [
        lambda request: static('css/dist/styles.css'),
    ],
    'SCRIPTS': [
        lambda request: 'https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;700&family=Lora:wght@400;500;700&display=swap',
    ],
}
```

- [ ] **Step 5: Verify admin renders**

Run:

```bash
.venv/bin/python manage.py shell -c "
from django.test import Client
c = Client()
r = c.get('/admin/login/', HTTP_HOST='127.0.0.1')
print(r.status_code)
"
```
Expected: `200`.

---

### Task 8: Manual end-to-end verification

**Files:** none new.

- [ ] **Step 1: Create a platform admin superuser**

Run:

```bash
.venv/bin/python manage.py shell -c "
from accounts.models import User
u = User.objects.create_superuser(email='admin@s9.local', password='adminpass123', role='platform_admin')
print('created', u.email, u.role)
"
```

- [ ] **Step 2: Verify platform admin can access `/admin/login/` and is prompted for 2FA setup on first login**

Use the test client or dev server to log in and complete email OTP setup.

- [ ] **Step 3: Create a tenant via shell**

```bash
.venv/bin/python manage.py shell -c "
from tenants.models import Tenant
t = Tenant.objects.create(name='Sage Nine Creative', slug='sage-nine')
print('created', t.slug)
"
```

- [ ] **Step 4: Create a tenant admin and verify they cannot access `/admin/`**

```bash
.venv/bin/python manage.py shell -c "
from accounts.models import User
from tenants.models import Tenant
t = Tenant.objects.get(slug='sage-nine')
u = User.objects.create_user(email='ta@sage.local', password='tapass123', role='tenant_admin', tenant=t)
print('created', u.email, u.is_staff)
from django.test import Client
c = Client()
c.force_login(u)
r = c.get('/admin/', HTTP_HOST='127.0.0.1')
print('admin access status', r.status_code)
"
```
Expected: `is_staff False`, admin access status `302` to login or `403`.

- [ ] **Step 5: Run full test suite**

Run: `.venv/bin/python manage.py test accounts.tests tenants.tests -v 2`
Expected: all tests PASS.

---

## Self-Review

- **Spec coverage:**
  - Custom User with roles/tenant: Tasks 3 and 7.
  - Tenant model + isolation helpers: Tasks 2 and 7.
  - TenantMiddleware path/subdomain: Task 4.
  - 2FA for platform admins: Tasks 5 and 8.
  - Admin access restricted to platform admins: Tasks 5 and 7.
  - Unfold branding: Task 7.
  - Public placeholder: Task 6.
- **Placeholder scan:** no TBD/TODO; all steps include exact file paths and code.
- **Type consistency:** `request.tenant`, `User.Role` choices, and `Tenant.slug` are consistent across tasks.
- **One gap found:** the `User` model `save()` sets `is_staff` silently. This is acceptable for Foundation, but note it in a code comment.

No additional tasks needed.
