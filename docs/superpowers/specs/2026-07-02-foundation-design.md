# Foundation Milestone Design — Multi-Tenant Booking Platform

**Date:** 2026-07-02  
**Status:** Approved  
**Scope:** Authentication, tenancy, row-level isolation, Django admin shell, and Sage Nine Creative branding.  

> **Note:** UI, template location, Tailwind configuration, and `.env` handling decisions in this document are superseded by `docs/superpowers/specs/2026-07-03-tailwind-ui-refactor-design.md`.

This milestone implements the foundation on which all later booking, payment, calendar, and integration features will be built.

---

## 1. Goals & Boundaries

### In scope

- Custom `User` model with roles and optional tenant attachment.
- `Tenant` model with branding/config storage.
- Row-level tenant isolation helpers (`TenantMixin`, `TenantQuerySet`).
- `TenantMiddleware` that resolves tenant from URL path or subdomain.
- Two-factor authentication for platform admin access via `django-two-factor-auth` (TOTP + email OTP).
- Restrict Django admin access to platform admins only.
- Unfold-styled admin for `User` and `Tenant` with Sage Nine Creative brand colors and fonts.
- Minimal public landing view that demonstrates tenant-aware rendering.
- Migrations, settings wiring, and verification commands (`check`, `migrate`, admin render test).

### Out of scope

- Event types, availability, or booking request flow.
- Google Calendar/Meet integration.
- Stripe Connect payments.
- Outbound webhooks, retries, delivery logs.
- Public booking pages or embed widget.
- Notifications engine (email/SMS beyond 2FA email OTP).
- Background job queue.

### Success criteria

1. `manage.py check` passes with the expected `staticfiles.W004` warning only.
2. `manage.py migrate` runs successfully.
3. `/admin/login/` renders with Sage Nine Creative colors and fonts.
4. Only a `platform_admin` user can log into `/admin/`.
5. Platform admin 2FA enrollment and verification works (email OTP in dev).
6. A `Tenant` and tenant-scoped `tenant_admin` user can be created via admin.
7. `TenantMiddleware` tests prove tenant resolution from both `/t/<slug>/` and subdomain `Host`.

---

## 2. Sub-Project Decomposition

The full PRD is intentionally split into milestone-aligned sub-projects:

| # | Milestone | Deliverables |
|---|-----------|--------------|
| 1 | **Foundation** (this doc) | Auth, tenancy, admin shell, branding |
| 2 | Booking Core | Event types, availability, booking states, approval queue, notifications |
| 3 | Google Integration | OAuth, busy read, placeholder/confirm events, Meet links |
| 4 | Payments | Stripe Connect, payment timing, fees, refunds |
| 5 | Integrations/Hardening | Outbound webhooks, retries, dashboards, embed widget |

Each milestone gets its own design doc and implementation plan.

---

## 3. Architecture

### App split

| App | Responsibility |
|-----|----------------|
| `accounts` | Custom `User`, role utilities, auth helpers |
| `tenants` | `Tenant` model, tenant resolution middleware, tenant-scoped mixin/queryset |

Keeping these separate makes `tenants` reusable by future apps (`bookings`, `payments`, `integrations`) without pulling in auth details.

### Tenancy model

- **Shared database, tenant-scoped rows.** Every tenant-scoped model inherits `TenantMixin` and carries an indexed `tenant_id` FK.
- **Resolution:** `TenantMiddleware` sets `request.tenant` from URL path (`/t/<slug>/`) first, then falls back to subdomain.
- **Admin filtering:** Tenant admins and tenant staff see only rows belonging to `request.user.tenant`. Platform admins see all rows and can filter by tenant.

### 2FA model

- `django-two-factor-auth` provides TOTP and email OTP methods.
- `AdminSiteOTPRequired` enforces 2FA for anyone accessing `/admin/`.
- Standard (non-admin) login uses the same two-factor views, but 2FA setup is optional for tenants in this milestone.
- Email OTP is enabled in dev so platform admin 2FA can be tested without a phone/authenticator app.

---

## 4. Data Model

### `accounts.User`

Extends `AbstractUser`.

| Field | Type | Notes |
|-------|------|-------|
| `role` | `CharField(max_length=20, choices=ROLES)` | `platform_admin`, `tenant_admin`, `tenant_staff` |
| `tenant` | `ForeignKey(Tenant, null=True, blank=True, on_delete=models.SET_NULL)` | Null for platform admins |
| `is_staff` | `BooleanField` | Derived/kept in sync: `role == platform_admin` |
| `email` | inherited from `AbstractUser` | Login identifier |

Additional auth config:
- `USERNAME_FIELD = 'email'`
- `REQUIRED_FIELDS = []`

Constraints:
- `tenant` must be set when `role` is `tenant_admin` or `tenant_staff`.
- `tenant` must be null when `role` is `platform_admin`.
- Only `platform_admin` users receive `is_staff=True` (Django admin gate).

### `tenants.Tenant`

| Field | Type | Notes |
|-------|------|-------|
| `id` | `BigAutoField` primary key | |
| `name` | `CharField(max_length=255)` | Display name |
| `slug` | `SlugField(unique=True)` | Used in URLs and subdomain matching |
| `is_active` | `BooleanField(default=True)` | |
| `branding` | `JSONField(default=dict, blank=True)` | Colors, fonts, logo URL, custom CSS |
| `config` | `JSONField(default=dict, blank=True)` | Future feature toggles |
| `created_at` | `DateTimeField(auto_now_add=True)` | |
| `updated_at` | `DateTimeField(auto_now=True)` | |

### `tenants.TenantMixin`

Abstract model for all tenant-scoped tables.

| Field | Type | Notes |
|-------|------|-------|
| `tenant` | `ForeignKey(Tenant, on_delete=models.CASCADE, db_index=True)` | Required on child models |

Provides:
- Default manager/queryset via `TenantQuerySet`.
- `for_tenant(tenant)` queryset method.
- `for_request(request)` queryset method that reads `request.tenant`.

### `tenants.TenantMembership` (deferred)

Not needed in Foundation. Added later if a user must belong to multiple tenants.

---

## 5. Tenant Resolution

### `TenantMiddleware`

Order in `MIDDLEWARE`: after `AuthenticationMiddleware`, before any view-level tenant filtering.

Logic:
1. Skip resolution for platform-level URL prefixes: `/admin/`, `/accounts/`, `/two_factor/`, `/static/`, `/media/`.
2. Check request path for `/t/<slug>/`. If matched and tenant is active, set `request.tenant`.
3. Otherwise, split `Host` on `.`; if the first label matches an active tenant slug and the host is not the base domain, set `request.tenant`.
4. If no tenant matched, set `request.tenant = None`.

### Base domain configuration

Add `BASE_HOST` to settings (e.g., `s9booking.local` in dev). The middleware uses this to distinguish a tenant subdomain from the platform domain.

---

## 6. Two-Factor Authentication

### Packages

- `django-two-factor-auth~=1.17.0` (brings `django-otp`).
- No phonenumber plugin in Foundation; only TOTP and email OTP.

### `INSTALLED_APPS` additions

Place after `django.contrib.*` and before local apps:

```python
'django_otp',
'django_otp.plugins.otp_static',
'django_otp.plugins.otp_totp',
'django_otp.plugins.otp_email',
'two_factor',
'two_factor.plugins.email',
```

### `MIDDLEWARE` addition

```python
'django_otp.middleware.OTPMiddleware',
```
placed after `AuthenticationMiddleware`.

### Admin enforcement

In `config/urls.py`:

```python
from django.contrib import admin
from two_factor.admin import AdminSiteOTPRequired

admin.site.__class__ = AdminSiteOTPRequired
```

### Login URL

```python
LOGIN_URL = 'two_factor:login'
LOGIN_REDIRECT_URL = 'admin:index'
```

### Dev email backend

```python
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
DEFAULT_FROM_EMAIL = 'dev@s9booking.local'
```

---

## 7. Admin & Branding

### Access control

- Only `platform_admin` users are `is_staff=True`; Django admin permissions grant superuser-like access for platform management.
- A custom `UserAdmin` enforces that `is_staff` is set only when `role == platform_admin`.
- Tenant admins and tenant staff cannot access `/admin/`.

### `accounts.UserAdmin`

- List display: `email`, `role`, `tenant`, `is_active`, `date_joined`.
- Filters: `role`, `tenant__is_active`.
- Fieldsets: standard auth fields + `role` + `tenant`.
- Save validation: raise `ValidationError` if `tenant` and `role` constraints are violated.

### `tenants.TenantAdmin`

- List display: `name`, `slug`, `is_active`, `created_at`.
- Search: `name`, `slug`.
- Editable `branding` and `config` JSON fields (Unfold styled).

### Unfold brand configuration

Update `UNFOLD` in `config/settings/base.py`:

- Primary color: `#50665A` (Deep Sage)
- Secondary colors: `#333333` (Charcoal), `#CC7755` (Terracotta), `#F8F8F0` (Pale Cream)
- Fonts: load DM Sans (400, 500, 700) and Lora (400, 500, 700) via Google Fonts in `STYLES`/`SCRIPTS`.
- Sidebar: add `Tenants` and `Users` navigation items.

---

## 8. Public Placeholder

A single `home` view at `/`:

- If `request.tenant` is set, renders the tenant name and a styled welcome message.
- If no tenant, renders the platform landing page with Sage Nine Creative branding.
- No other public URLs in Foundation.

---

## 9. Settings Changes

### `requirements.txt`

Add:

```text
django-two-factor-auth~=1.17.0
```

### `.env` additions for dev

```text
BASE_HOST=s9booking.local
DEFAULT_FROM_EMAIL=dev@s9booking.local
```

### `config/settings/base.py`

- Add 2FA apps and middleware.
- Add `BASE_HOST` env read.
- Set `LOGIN_URL`, `LOGIN_REDIRECT_URL`.
- Configure `UNFOLD` colors/fonts and sidebar.
- Add `DEFAULT_FROM_EMAIL`.

### `config/urls.py`

- Apply `AdminSiteOTPRequired`.
- Include `two_factor.urls` under `accounts/`.
- Add the public `home` view at `/`.

---

## 10. Verification Plan

After implementation, run:

```bash
.venv/bin/python manage.py check
.venv/bin/python manage.py migrate
```

Then manually or via a small test script:

1. Create a `platform_admin` user through a shell or migration.
2. Visit `/admin/login/` and verify 2FA setup flow (email OTP).
3. Create a `Tenant` via `/admin/tenants/tenant/`.
4. Create a `tenant_admin` user scoped to that tenant; verify they cannot access `/admin/`.
5. Run middleware unit tests for path-based and subdomain-based tenant resolution.

---

## 11. Out-of-Scope Reminders

- No booking, calendar, payment, webhook, or embed functionality.
- No multi-tenant membership (one tenant per user in Foundation).
- No phone/SMS 2FA.
- No background workers.

---

## 12. Open Questions / Future Decisions

- Should tenant users eventually log in via a tenant-specific URL (`/t/<slug>/accounts/login/`)? Defer to Booking Core.
- Should `Tenant.branding` include a logo upload field? Defer; use JSON string URL for now.
- Should platform admin superusers also require 2FA? Yes, via `AdminSiteOTPRequired`.
