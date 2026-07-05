# Booking Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Booking Core milestone: configurable event types, staff profiles with working hours and time-off, timezone-aware availability computation, the booking request state machine, a public booking page, a tenant-scoped staff approval dashboard with config pages, and email notifications on state transitions.

**Architecture:** One new `bookings` Django app with four models (`StaffProfile`, `StaffTimeOff`, `EventType`, `BookingRequest`), a `SlotProvider` protocol for availability computation, server-rendered Django views for public booking and staff dashboard, and sync email notifications via a `notify()` hook. All tenant-scoped via `TenantMixin`.

**Tech Stack:** Django 6.0, django-unfold, django-tailwind v4, django-two-factor-auth, environs, SQLite (dev).

## Global Constraints

- Django virtualenv lives at `.venv/`; use `.venv/bin/python manage.py <cmd>`.
- `unfold` and its contrib apps must stay **before** `django.contrib.admin` in `INSTALLED_APPS`.
- `django_otp.middleware.OTPMiddleware` must be placed after `AuthenticationMiddleware`.
- `SECRET_KEY`, `DEBUG`, and `ALLOWED_HOSTS` are required in `.env`.
- `staticfiles.W004` warning is expected and must not be "fixed" by removing the setting.
- No test suite/linter/typechecker is configured; verification is manual via `manage.py check`, `manage.py migrate`, and targeted Django TestCase checks.
- Brand colors: Deep Sage `#50665A`, Charcoal `#333333`, Terracotta `#CC7755`, Pale Cream `#F8F8F0`. Fonts: DM Sans and Lora.
- Tailwind v4 configuration lives in CSS only — no `tailwind.config.js`.
- No inline `<style>` blocks. No hand-authored `.css` files outside of `theme/static_src/src/styles.css`.
- `.env.example` is committed; `.env` is local-only.

---

## File Structure

| File | Responsibility |
|------|---------------|
| `bookings/__init__.py` | App init |
| `bookings/apps.py` | App config |
| `bookings/models.py` | `StaffProfile`, `StaffTimeOff`, `EventType`, `BookingRequest`, `BookingRequest.Status`, `TransitionError` |
| `bookings/admin.py` | Unfold admin for all models (platform-admin-only) |
| `bookings/urls.py` | All booking routes |
| `bookings/views.py` | All views (public + staff + config) |
| `bookings/forms.py` | Django forms for booking submission, event type CRUD, staff profile, time-off |
| `bookings/slots.py` | `SlotProvider` protocol, `WorkingHoursSlotProvider`, `compute_available_slots`, `BusyInterval` |
| `bookings/notifications.py` | `notify(booking, event)` |
| `bookings/exceptions.py` | `TransitionError` |
| `bookings/templates/bookings/tenant_home.html` | Event type list |
| `bookings/templates/bookings/booking_create.html` | Slot picker + intake form |
| `bookings/templates/bookings/booking_success.html` | Confirmation |
| `bookings/templates/bookings/staff_dashboard.html` | Grouped bookings |
| `bookings/templates/bookings/booking_detail.html` | Detail + action buttons |
| `bookings/templates/bookings/event_type_list.html`, `_form.html`, `_confirm_delete.html` | EventType CRUD |
| `bookings/templates/bookings/staff_profile_edit.html` | Working hours editor |
| `bookings/templates/bookings/staff_time_off_list.html`, `_form.html`, `_confirm_delete.html` | Time-off CRUD |
| `bookings/templates/bookings/tenant_settings.html` | Tenant settings |
| `bookings/templates/bookings/emails/*.txt,*.html` | Email templates |
| `bookings/tests/test_models.py` | Model field validation, `booking_ref` generation, `TenantMixin` filtering |
| `bookings/tests/test_state_machine.py` | State transitions, `TransitionError`, `notify()` calls |
| `bookings/tests/test_slots.py` | `WorkingHoursSlotProvider`, `compute_available_slots` |
| `bookings/tests/test_views.py` | Public booking, staff dashboard access control, action views, config views |
| `bookings/tests/test_notifications.py` | `notify()` dispatch, `BOOKING_NOTIFICATIONS_ENABLED` |
| `bookings/tests/test_signals.py` | Auto-provisioned `StaffProfile` |
| `accounts/signals.py` | `create_staff_profile_for_tenant_user` |
| `accounts/apps.py` | Wire signal in `ready()` |
| `tenants/models.py` | Add `timezone` field to `Tenant` |
| `config/settings/base.py` | Add `bookings` to `INSTALLED_APPS`, add `BOOKING_NOTIFICATIONS_ENABLED`, `DEFAULT_SLOT_PROVIDER` |
| `config/urls.py` | Include `bookings.urls` under `/t/<slug>/` |

---

### Task 1: Scaffold `bookings` app

**Files:**
- Create: `bookings/__init__.py`, `bookings/apps.py`
- Modify: `config/settings/base.py` (register app)

**Interfaces:**
- Produces: `bookings` registered in `INSTALLED_APPS`.

- [ ] **Step 1: Create `bookings/apps.py`**

```python
from django.apps import AppConfig


class BookingsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'bookings'
```

- [ ] **Step 2: Create `bookings/__init__.py`**

```python
default_app_config = 'bookings.apps.BookingsConfig'
```

- [ ] **Step 3: Register app in `config/settings/base.py`**

Add `'bookings'` under `# Local apps` after `tenants`:

```python
    # Local apps
    'tailwind',
    'theme',
    'accounts',
    'tenants',
    'bookings',
```

- [ ] **Step 4: Run `check` to verify app registration**

Run: `.venv/bin/python manage.py check`
Expected: passes with only `staticfiles.W004` warning.

- [ ] **Step 5: Commit**

```bash
git add bookings/__init__.py bookings/apps.py config/settings/base.py
git commit -m "feat: scaffold bookings app"
```

---

### Task 2: Add `Tenant.timezone` field

**Files:**
- Modify: `tenants/models.py`

**Interfaces:**
- Produces: `Tenant.timezone` CharField (default `'UTC'`).

- [ ] **Step 1: Write failing test in `tenants/tests.py`**

Append to `tenants/tests.py`:

```python
from tenants.models import Tenant


class TenantTimezoneTests(TestCase):
    def test_default_timezone_is_utc(self):
        tenant = Tenant.objects.create(name='Test', slug='test')
        self.assertEqual(tenant.timezone, 'UTC')
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python manage.py test tenants.tests.TenantTimezoneTests -v 2`
Expected: FAIL — `timezone` field not defined.

- [ ] **Step 3: Add `timezone` field to `tenants/models.py`**

Add to `Tenant` model:

```python
    timezone = models.CharField(max_length=64, default='UTC')
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python manage.py test tenants.tests.TenantTimezoneTests -v 2`
Expected: PASS.

- [ ] **Step 5: Make migrations**

Run: `.venv/bin/python manage.py makemigrations tenants`
Expected: creates migration adding `timezone` field.

- [ ] **Step 6: Commit**

```bash
git add tenants/models.py tenants/tests.py tenants/migrations/
git commit -m "feat: add Tenant.timezone field"
```

---

### Task 3: Build `bookings.exceptions` and `BookingRequest.Status`

**Files:**
- Create: `bookings/exceptions.py`
- Create: `bookings/models.py` (partial — just `Status` choices and `TransitionError`)

**Interfaces:**
- Produces: `TransitionError` exception, `BookingRequest.Status` choices.

- [ ] **Step 1: Create `bookings/exceptions.py`**

```python
class TransitionError(ValueError):
    """Raised when an illegal state transition is attempted."""
    pass
```

- [ ] **Step 2: Create `bookings/models.py` with `Status` choices**

```python
from django.db import models
from bookings.exceptions import TransitionError


class BookingRequest(models.Model):
    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        PENDING = 'pending', 'Pending'
        AWAITING_PAYMENT = 'awaiting_payment', 'Awaiting Payment'
        APPROVED = 'approved', 'Approved'
        REJECTED = 'rejected', 'Rejected'
        CANCELED = 'canceled', 'Canceled'
        COMPLETED = 'completed', 'Completed'
```

- [ ] **Step 3: Commit**

```bash
git add bookings/exceptions.py bookings/models.py
git commit -m "feat: add TransitionError and BookingRequest.Status"
```

---

### Task 4: Build `bookings.StaffProfile` model

**Files:**
- Create: `bookings/models.py` (add `StaffProfile`)
- Create: `bookings/tests/test_models.py` (partial)

**Interfaces:**
- Produces: `StaffProfile` model with `user`, `working_hours`, `is_active`, `tenant` (via `TenantMixin`).

- [ ] **Step 1: Write failing test in `bookings/tests/test_models.py`**

Create `bookings/tests/__init__.py` and `bookings/tests/test_models.py`:

```python
from django.test import TestCase
from accounts.models import User
from tenants.models import Tenant
from bookings.models import StaffProfile


class StaffProfileModelTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name='Test', slug='test')
        self.user = User.objects.create_user(
            email='staff@test.com',
            password='test',
            role=User.Role.TENANT_STAFF,
            tenant=self.tenant,
        )

    def test_staff_profile_creation(self):
        profile = StaffProfile.objects.create(user=self.user, tenant=self.tenant)
        self.assertEqual(profile.user, self.user)
        self.assertTrue(profile.is_active)
        self.assertEqual(profile.working_hours, {})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python manage.py test bookings.tests.test_models.StaffProfileModelTests -v 2`
Expected: FAIL — `StaffProfile` not defined.

- [ ] **Step 3: Add `StaffProfile` to `bookings/models.py`**

```python
from tenants.models import TenantMixin


class StaffProfile(TenantMixin):
    user = models.OneToOneField(
        'accounts.User',
        on_delete=models.CASCADE,
    )
    working_hours = models.JSONField(default=dict)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['user__email']

    def __str__(self):
        return f'{self.user.email} ({self.tenant.name})'
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python manage.py test bookings.tests.test_models.StaffProfileModelTests -v 2`
Expected: PASS.

- [ ] **Step 5: Make migrations**

Run: `.venv/bin/python manage.py makemigrations bookings`
Expected: creates `bookings/migrations/0001_initial.py` with `StaffProfile`.

- [ ] **Step 6: Commit**

```bash
git add bookings/models.py bookings/tests/test_models.py bookings/migrations/
git commit -m "feat: add StaffProfile model"
```

---

### Task 5: Build `bookings.StaffTimeOff` model

**Files:**
- Create: `bookings/models.py` (add `StaffTimeOff`)
- Create: `bookings/tests/test_models.py` (extend)

**Interfaces:**
- Produces: `StaffTimeOff` model with `staff`, `date`, `all_day`, `start_time`, `end_time`, `reason`.

- [ ] **Step 1: Write failing test in `bookings/tests/test_models.py`**

Append:

```python
from datetime import date, time
from bookings.models import StaffTimeOff


class StaffTimeOffModelTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name='Test', slug='test')
        self.user = User.objects.create_user(
            email='staff@test.com',
            password='test',
            role=User.Role.TENANT_STAFF,
            tenant=self.tenant,
        )
        self.profile = StaffProfile.objects.create(user=self.user, tenant=self.tenant)

    def test_time_off_creation(self):
        time_off = StaffTimeOff.objects.create(
            staff=self.profile,
            tenant=self.tenant,
            date=date(2026, 7, 10),
            all_day=True,
            reason='Vacation',
        )
        self.assertTrue(time_off.all_day)
        self.assertEqual(time_off.reason, 'Vacation')

    def test_partial_time_off_requires_times(self):
        time_off = StaffTimeOff(
            staff=self.profile,
            tenant=self.tenant,
            date=date(2026, 7, 10),
            all_day=False,
        )
        with self.assertRaises(Exception):
            time_off.full_clean()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python manage.py test bookings.tests.test_models.StaffTimeOffModelTests -v 2`
Expected: FAIL — `StaffTimeOff` not defined.

- [ ] **Step 3: Add `StaffTimeOff` to `bookings/models.py`**

```python
class StaffTimeOff(TenantMixin):
    staff = models.ForeignKey(
        StaffProfile,
        on_delete=models.CASCADE,
        related_name='time_off',
    )
    date = models.DateField()
    all_day = models.BooleanField(default=True)
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)
    reason = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ['date']
        unique_together = [('staff', 'date')]

    def clean(self):
        super().clean()
        if not self.all_day and (self.start_time is None or self.end_time is None):
            from django.core.exceptions import ValidationError
            raise ValidationError('Partial time-off requires start_time and end_time.')
        if self.start_time and self.end_time and self.start_time >= self.end_time:
            from django.core.exceptions import ValidationError
            raise ValidationError('start_time must be before end_time.')

    def __str__(self):
        return f'{self.staff.user.email} - {self.date} ({self.reason or "blocked"})'
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python manage.py test bookings.tests.test_models.StaffTimeOffModelTests -v 2`
Expected: PASS.

- [ ] **Step 5: Make migrations**

Run: `.venv/bin/python manage.py makemigrations bookings`
Expected: adds `StaffTimeOff` model.

- [ ] **Step 6: Commit**

```bash
git add bookings/models.py bookings/tests/test_models.py bookings/migrations/
git commit -m "feat: add StaffTimeOff model"
```

---

### Task 6: Build `bookings.EventType` model

**Files:**
- Create: `bookings/models.py` (add `EventType`)
- Create: `bookings/tests/test_models.py` (extend)

**Interfaces:**
- Produces: `EventType` model with all fields from spec.

- [ ] **Step 1: Write failing test in `bookings/tests/test_models.py`**

Append:

```python
from decimal import Decimal
from bookings.models import EventType


class EventTypeModelTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name='Test', slug='test')
        self.user = User.objects.create_user(
            email='staff@test.com',
            password='test',
            role=User.Role.TENANT_STAFF,
            tenant=self.tenant,
        )
        self.profile = StaffProfile.objects.create(user=self.user, tenant=self.tenant)

    def test_event_type_creation(self):
        event_type = EventType.objects.create(
            tenant=self.tenant,
            name='Intro Call',
            slug='intro-call',
            duration_minutes=30,
            assigned_staff=self.profile,
        )
        self.assertEqual(event_type.slug, 'intro-call')
        self.assertTrue(event_type.approval_required)
        self.assertEqual(event_type.price_amount, Decimal('0'))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python manage.py test bookings.tests.test_models.EventTypeModelTests -v 2`
Expected: FAIL — `EventType` not defined.

- [ ] **Step 3: Add `EventType` to `bookings/models.py`**

```python
class EventType(TenantMixin):
    class PaymentMode(models.TextChoices):
        NO_PAYMENT = 'no_payment', 'No Payment'
        PAY_AT_REQUEST = 'pay_at_request', 'Pay at Request'
        PAY_AFTER_APPROVAL = 'pay_after_approval', 'Pay After Approval'

    name = models.CharField(max_length=255)
    slug = models.SlugField()
    description = models.TextField(blank=True)
    duration_minutes = models.PositiveIntegerField()
    buffer_minutes = models.PositiveIntegerField(default=0)
    price_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    currency = models.CharField(max_length=3, default='USD')
    payment_mode = models.CharField(
        max_length=20,
        choices=PaymentMode.choices,
        default=PaymentMode.NO_PAYMENT,
    )
    approval_required = models.BooleanField(default=True)
    location = models.CharField(max_length=255, blank=True)
    assigned_staff = models.ForeignKey(
        StaffProfile,
        on_delete=models.PROTECT,
    )
    intake_fields = models.JSONField(default=list)
    cancellation_policy = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['name']
        unique_together = [('tenant', 'slug')]

    def __str__(self):
        return self.name
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python manage.py test bookings.tests.test_models.EventTypeModelTests -v 2`
Expected: PASS.

- [ ] **Step 5: Make migrations**

Run: `.venv/bin/python manage.py makemigrations bookings`
Expected: adds `EventType` model.

- [ ] **Step 6: Commit**

```bash
git add bookings/models.py bookings/tests/test_models.py bookings/migrations/
git commit -m "feat: add EventType model"
```

---

### Task 7: Build `bookings.BookingRequest` model and state machine

**Files:**
- Create: `bookings/models.py` (add `BookingRequest` with transition methods)
- Create: `bookings/tests/test_state_machine.py`

**Interfaces:**
- Produces: `BookingRequest` model with `booking_ref`, `status`, transition methods (`submit`, `approve`, `reject`, `cancel`, `mark_completed`, `mark_paid`).

- [ ] **Step 1: Write failing test in `bookings/tests/test_state_machine.py`**

Create `bookings/tests/test_state_machine.py`:

```python
from django.test import TestCase
from django.utils import timezone
from accounts.models import User
from tenants.models import Tenant
from bookings.models import StaffProfile, EventType, BookingRequest
from bookings.exceptions import TransitionError


class BookingStateMachineTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name='Test', slug='test')
        self.user = User.objects.create_user(
            email='staff@test.com',
            password='test',
            role=User.Role.TENANT_STAFF,
            tenant=self.tenant,
        )
        self.profile = StaffProfile.objects.create(user=self.user, tenant=self.tenant)
        self.event_type = EventType.objects.create(
            tenant=self.tenant,
            name='Intro Call',
            slug='intro-call',
            duration_minutes=30,
            assigned_staff=self.profile,
        )

    def _create_booking(self, status=BookingRequest.Status.DRAFT):
        return BookingRequest.objects.create(
            tenant=self.tenant,
            event_type=self.event_type,
            staff=self.profile,
            status=status,
            start_at=timezone.now() + timezone.timedelta(days=1),
            end_at=timezone.now() + timezone.timedelta(days=1, hours=1),
            booker_name='Test Booker',
            booker_email='booker@test.com',
        )

    def test_submit_from_draft_to_pending(self):
        booking = self._create_booking(BookingRequest.Status.DRAFT)
        booking.submit()
        booking.refresh_from_db()
        self.assertEqual(booking.status, BookingRequest.Status.PENDING)

    def test_approve_from_pending_to_approved(self):
        booking = self._create_booking(BookingRequest.Status.PENDING)
        booking.approve()
        booking.refresh_from_db()
        self.assertEqual(booking.status, BookingRequest.Status.APPROVED)

    def test_reject_from_pending_to_rejected(self):
        booking = self._create_booking(BookingRequest.Status.PENDING)
        booking.reject()
        booking.refresh_from_db()
        self.assertEqual(booking.status, BookingRequest.Status.REJECTED)

    def test_illegal_transition_raises(self):
        booking = self._create_booking(BookingRequest.Status.APPROVED)
        with self.assertRaises(TransitionError):
            booking.reject()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python manage.py test bookings.tests.test_state_machine -v 2`
Expected: FAIL — `BookingRequest` model incomplete.

- [ ] **Step 3: Add `BookingRequest` to `bookings/models.py`**

```python
from django.utils import timezone as tz


class BookingRequest(TenantMixin):
    booking_ref = models.CharField(max_length=20, unique=True)
    event_type = models.ForeignKey(
        EventType,
        on_delete=models.PROTECT,
    )
    staff = models.ForeignKey(
        StaffProfile,
        on_delete=models.PROTECT,
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    start_at = models.DateTimeField()
    end_at = models.DateTimeField()
    booker_name = models.CharField(max_length=255)
    booker_email = models.EmailField()
    booker_timezone = models.CharField(max_length=64, default='UTC')
    booker_notes = models.TextField(blank=True)
    intake_responses = models.JSONField(default=dict)
    price_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    currency = models.CharField(max_length=3, default='USD')
    payment_mode = models.CharField(
        max_length=20,
        choices=EventType.PaymentMode.choices,
        default=EventType.PaymentMode.NO_PAYMENT,
    )
    payment_status = models.CharField(
        max_length=20,
        choices=[
            ('unpaid', 'Unpaid'),
            ('paid', 'Paid'),
            ('refunded', 'Refunded'),
        ],
        default='unpaid',
    )
    google_event_id = models.CharField(blank=True)
    meet_url = models.URLField(blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.booking_ref} - {self.booker_name}'

    def save(self, *args, **kwargs):
        if not self.booking_ref:
            # Will be set by pre_save signal after first save
            pass
        super().save(*args, **kwargs)

    def _transition(self, new_status, guard=None):
        if guard:
            guard()
        self.status = new_status
        self.save(update_fields=['status', 'updated_at'])

    def submit(self):
        if self.status != self.Status.DRAFT:
            raise TransitionError(f'Cannot submit from {self.status}')
        if not self.start_at or not self.end_at or not self.booker_email:
            raise TransitionError('Missing required fields for submission')
        target = self.Status.PENDING if self.event_type.approval_required else self.Status.APPROVED
        self._transition(target)
        from bookings.notifications import notify
        notify(self, 'booking.created')

    def approve(self):
        if self.status != self.Status.PENDING:
            raise TransitionError(f'Cannot approve from {self.status}')
        target = self.Status.AWAITING_PAYMENT if self.payment_mode == EventType.PaymentMode.PAY_AFTER_APPROVAL else self.Status.APPROVED
        self._transition(target)
        from bookings.notifications import notify
        notify(self, 'booking.approved')

    def reject(self):
        if self.status != self.Status.PENDING:
            raise TransitionError(f'Cannot reject from {self.status}')
        self._transition(self.Status.REJECTED)
        from bookings.notifications import notify
        notify(self, 'booking.rejected')

    def cancel(self):
        if self.status not in (self.Status.PENDING, self.Status.AWAITING_PAYMENT, self.Status.APPROVED):
            raise TransitionError(f'Cannot cancel from {self.status}')
        self._transition(self.Status.CANCELED)
        from bookings.notifications import notify
        notify(self, 'booking.canceled')

    def mark_completed(self):
        if self.status != self.Status.APPROVED:
            raise TransitionError(f'Cannot mark completed from {self.status}')
        if self.start_at > tz.now():
            raise TransitionError('Cannot complete a future booking')
        self._transition(self.Status.COMPLETED)
        from bookings.notifications import notify
        notify(self, 'booking.completed')

    def mark_paid(self):
        if self.status != self.Status.AWAITING_PAYMENT:
            raise TransitionError(f'Cannot mark paid from {self.status}')
        if self.payment_status != 'paid':
            raise TransitionError('payment_status must be paid before calling mark_paid')
        self._transition(self.Status.APPROVED)
        from bookings.notifications import notify
        notify(self, 'payment.succeeded')
```

- [ ] **Step 4: Add `booking_ref` generation signal**

Add to `bookings/models.py` (or `bookings/signals.py`):

```python
from django.db.models.signals import pre_save
from django.dispatch import receiver


@receiver(pre_save, sender=BookingRequest)
def set_booking_ref(sender, instance, **kwargs):
    if not instance.booking_ref:
        if instance.pk:
            instance.booking_ref = f'BKG-{instance.pk:06d}'
        else:
            instance.booking_ref = 'BKG-000000'  # Will be updated after first save
```

Actually, simpler: generate after first save. Let me use a `post_save` signal instead:

```python
from django.db.models.signals import post_save
from django.dispatch import receiver


@receiver(post_save, sender=BookingRequest)
def set_booking_ref_after_save(sender, instance, created, **kwargs):
    if created and instance.booking_ref == 'BKG-000000':
        instance.booking_ref = f'BKG-{instance.pk:06d}'
        BookingRequest.objects.filter(pk=instance.pk).update(booking_ref=instance.booking_ref)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/bin/python manage.py test bookings.tests.test_state_machine -v 2`
Expected: PASS.

- [ ] **Step 6: Make migrations**

Run: `.venv/bin/python manage.py makemigrations bookings`
Expected: adds `BookingRequest` model.

- [ ] **Step 7: Commit**

```bash
git add bookings/models.py bookings/tests/test_state_machine.py bookings/migrations/
git commit -m "feat: add BookingRequest model and state machine"
```

---

### Task 8: Build `bookings.StaffProfile` auto-provision signal

**Files:**
- Create: `accounts/signals.py`
- Modify: `accounts/apps.py`

**Interfaces:**
- Consumes: `accounts.User` post_save signal.
- Produces: Auto-created `StaffProfile` for `tenant_admin`/`tenant_staff`.

- [ ] **Step 1: Write failing test in `bookings/tests/test_signals.py`**

Create `bookings/tests/test_signals.py`:

```python
from django.test import TestCase
from accounts.models import User
from tenants.models import Tenant
from bookings.models import StaffProfile


class StaffProfileAutoProvisionTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name='Test', slug='test')

    def test_tenant_admin_gets_staff_profile(self):
        user = User.objects.create_user(
            email='admin@test.com',
            password='test',
            role=User.Role.TENANT_ADMIN,
            tenant=self.tenant,
        )
        self.assertTrue(StaffProfile.objects.filter(user=user).exists())
        profile = StaffProfile.objects.get(user=user)
        self.assertEqual(profile.working_hours, {
            0: [{'start': '09:00', 'end': '17:00'}],
            1: [{'start': '09:00', 'end': '17:00'}],
            2: [{'start': '09:00', 'end': '17:00'}],
            3: [{'start': '09:00', 'end': '17:00'}],
            4: [{'start': '09:00', 'end': '17:00'}],
        })

    def test_platform_admin_does_not_get_profile(self):
        user = User.objects.create_user(
            email='platform@test.com',
            password='test',
            role=User.Role.PLATFORM_ADMIN,
        )
        self.assertFalse(StaffProfile.objects.filter(user=user).exists())

    def test_idempotent_on_resave(self):
        user = User.objects.create_user(
            email='admin@test.com',
            password='test',
            role=User.Role.TENANT_ADMIN,
            tenant=self.tenant,
        )
        count = StaffProfile.objects.filter(user=user).count()
        user.save()
        self.assertEqual(StaffProfile.objects.filter(user=user).count(), count)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python manage.py test bookings.tests.test_signals -v 2`
Expected: FAIL — signal not wired.

- [ ] **Step 3: Create `accounts/signals.py`**

```python
from django.db.models.signals import post_save
from django.dispatch import receiver
from accounts.models import User


@receiver(post_save, sender=User)
def create_staff_profile_for_tenant_user(sender, instance, **kwargs):
    if instance.role in (User.Role.TENANT_ADMIN, User.Role.TENANT_STAFF) and instance.tenant is not None:
        from bookings.models import StaffProfile
        StaffProfile.objects.get_or_create(
            user=instance,
            defaults={
                'tenant': instance.tenant,
                'working_hours': {
                    0: [{'start': '09:00', 'end': '17:00'}],
                    1: [{'start': '09:00', 'end': '17:00'}],
                    2: [{'start': '09:00', 'end': '17:00'}],
                    3: [{'start': '09:00', 'end': '17:00'}],
                    4: [{'start': '09:00', 'end': '17:00'}],
                },
            },
        )
```

- [ ] **Step 4: Wire signal in `accounts/apps.py`**

```python
from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'accounts'

    def ready(self):
        import accounts.signals  # noqa: F401
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/bin/python manage.py test bookings.tests.test_signals -v 2`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add accounts/signals.py accounts/apps.py bookings/tests/test_signals.py
git commit -m "feat: auto-provision StaffProfile for tenant users"
```

---

### Task 9: Build `bookings.slots` (SlotProvider protocol + WorkingHoursSlotProvider)

**Files:**
- Create: `bookings/slots.py`
- Create: `bookings/tests/test_slots.py`

**Interfaces:**
- Produces: `SlotProvider` protocol, `WorkingHoursSlotProvider`, `compute_available_slots()`, `BusyInterval`.

- [ ] **Step 1: Write failing test in `bookings/tests/test_slots.py`**

Create `bookings/tests/test_slots.py`:

```python
from datetime import date, datetime, time
from django.test import TestCase
from django.utils import timezone
from accounts.models import User
from tenants.models import Tenant
from bookings.models import StaffProfile, StaffTimeOff, EventType
from bookings.slots import WorkingHoursSlotProvider, compute_available_slots


class WorkingHoursSlotProviderTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name='Test', slug='test', timezone='US/Eastern')
        self.user = User.objects.create_user(
            email='staff@test.com',
            password='test',
            role=User.Role.TENANT_STAFF,
            tenant=self.tenant,
        )
        self.profile = StaffProfile.objects.create(
            user=self.user,
            tenant=self.tenant,
            working_hours={
                0: [{'start': '09:00', 'end': '17:00'}],  # Monday
                1: [{'start': '09:00', 'end': '17:00'}],
                2: [{'start': '09:00', 'end': '17:00'}],
                3: [{'start': '09:00', 'end': '17:00'}],
                4: [{'start': '09:00', 'end': '17:00'}],
            },
        )
        self.provider = WorkingHoursSlotProvider()

    def test_working_day_has_gaps_outside_hours(self):
        # Monday 2026-07-06
        start = datetime(2026, 7, 6, 0, 0, tzinfo=timezone.utc)
        end = datetime(2026, 7, 7, 0, 0, tzinfo=timezone.utc)
        busy = self.provider.compute_busy(self.profile, start, end)
        # Should have gaps: midnight-9am and 5pm-midnight (in UTC, adjusted for Eastern)
        self.assertTrue(len(busy) > 0)

    def test_weekend_is_all_busy(self):
        # Saturday 2026-07-11
        start = datetime(2026, 7, 11, 0, 0, tzinfo=timezone.utc)
        end = datetime(2026, 7, 12, 0, 0, tzinfo=timezone.utc)
        busy = self.provider.compute_busy(self.profile, start, end)
        # Entire day should be busy (no working hours)
        self.assertTrue(len(busy) > 0)

    def test_time_off_excludes_slots(self):
        StaffTimeOff.objects.create(
            staff=self.profile,
            tenant=self.tenant,
            date=date(2026, 7, 6),
            all_day=True,
            reason='Vacation',
        )
        start = datetime(2026, 7, 6, 0, 0, tzinfo=timezone.utc)
        end = datetime(2026, 7, 7, 0, 0, tzinfo=timezone.utc)
        busy = self.provider.compute_busy(self.profile, start, end)
        # Should include time-off interval
        self.assertTrue(any(b.source == 'time_off' for b in busy))


class ComputeAvailableSlotsTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name='Test', slug='test', timezone='UTC')
        self.user = User.objects.create_user(
            email='staff@test.com',
            password='test',
            role=User.Role.TENANT_STAFF,
            tenant=self.tenant,
        )
        self.profile = StaffProfile.objects.create(
            user=self.user,
            tenant=self.tenant,
            working_hours={
                0: [{'start': '09:00', 'end': '17:00'}],
            },
        )
        self.event_type = EventType.objects.create(
            tenant=self.tenant,
            name='Test',
            slug='test',
            duration_minutes=30,
            buffer_minutes=0,
            assigned_staff=self.profile,
        )

    def test_slots_only_during_working_hours(self):
        slots = compute_available_slots(self.event_type, self.profile, date(2026, 7, 6))
        # Monday 2026-07-06, 9am-5pm UTC, 30-min slots
        self.assertTrue(len(slots) > 0)
        for slot in slots:
            self.assertGreaterEqual(slot.hour, 9)
            self.assertLess(slot.hour, 17)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python manage.py test bookings.tests.test_slots -v 2`
Expected: FAIL — `bookings.slots` not defined.

- [ ] **Step 3: Create `bookings/slots.py`**

```python
from datetime import datetime, timedelta, date, time
from typing import NamedTuple, Protocol, List
from zoneinfo import ZoneInfo


class BusyInterval(NamedTuple):
    start_at: datetime
    end_at: datetime
    source: str


class SlotProvider(Protocol):
    def compute_busy(
        self,
        staff: 'StaffProfile',
        start_at: datetime,
        end_at: datetime,
    ) -> List[BusyInterval]: ...


class WorkingHoursSlotProvider:
    def compute_busy(self, staff, start_at, end_at):
        from bookings.models import StaffTimeOff

        tenant_tz = ZoneInfo(staff.tenant.timezone)
        start_local = start_at.astimezone(tenant_tz)
        end_local = end_at.astimezone(tenant_tz)

        busy = []
        current_date = start_local.date()
        end_date = end_local.date()

        while current_date <= end_date:
            weekday = current_date.weekday()
            day_start = datetime.combine(current_date, time(0, 0), tzinfo=tenant_tz)
            day_end = datetime.combine(current_date, time(23, 59, 59), tzinfo=tenant_tz)

            hours = staff.working_hours.get(weekday, [])
            if not hours:
                # Entire day is busy
                busy.append(BusyInterval(day_start, day_end, 'working_hours_gap'))
            else:
                # Gap before first slot
                first_start = time.fromisoformat(hours[0]['start'])
                busy.append(BusyInterval(day_start, datetime.combine(current_date, first_start, tzinfo=tenant_tz), 'working_hours_gap'))
                # Gap after last slot
                last_end = time.fromisoformat(hours[-1]['end'])
                busy.append(BusyInterval(datetime.combine(current_date, last_end, tzinfo=tenant_tz), day_end, 'working_hours_gap'))

            # Time-off
            time_offs = StaffTimeOff.objects.filter(staff=staff, date=current_date)
            for to in time_offs:
                if to.all_day:
                    busy.append(BusyInterval(day_start, day_end, 'time_off'))
                else:
                    to_start = datetime.combine(current_date, to.start_time, tzinfo=tenant_tz)
                    to_end = datetime.combine(current_date, to.end_time, tzinfo=tenant_tz)
                    busy.append(BusyInterval(to_start, to_end, 'time_off'))

            current_date += timedelta(days=1)

        # Convert to UTC and clamp
        utc_busy = []
        for b in busy:
            b_start = b.start_at.astimezone(ZoneInfo('UTC'))
            b_end = b.end_at.astimezone(ZoneInfo('UTC'))
            # Clamp to [start_at, end_at]
            clamped_start = max(b_start, start_at)
            clamped_end = min(b_end, end_at)
            if clamped_start < clamped_end:
                utc_busy.append(BusyInterval(clamped_start, clamped_end, b.source))

        return sorted(utc_busy, key=lambda x: x.start_at)


def compute_available_slots(event_type, staff, date, granularity_minutes=30):
    tenant_tz = ZoneInfo(staff.tenant.timezone)
    day_start = datetime.combine(date, time(0, 0), tzinfo=tenant_tz)
    day_end = datetime.combine(date, time(23, 59, 59), tzinfo=tenant_tz)

    provider = WorkingHoursSlotProvider()
    busy = provider.compute_busy(staff, day_start, day_end)

    # Find free spans
    free_spans = []
    current = day_start
    for b in busy:
        if current < b.start_at:
            free_spans.append((current, b.start_at))
        current = max(current, b.end_at)
    if current < day_end:
        free_spans.append((current, day_end))

    # Generate slots
    slots = []
    duration = timedelta(minutes=event_type.duration_minutes + 2 * event_type.buffer_minutes)
    for span_start, span_end in free_spans:
        slot_start = span_start
        while slot_start + duration <= span_end:
            slots.append(slot_start.astimezone(ZoneInfo('UTC')))
            slot_start += timedelta(minutes=granularity_minutes)

    return slots
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python manage.py test bookings.tests.test_slots -v 2`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add bookings/slots.py bookings/tests/test_slots.py
git commit -m "feat: add SlotProvider protocol and WorkingHoursSlotProvider"
```

---

### Task 10: Build `bookings.notifications`

**Files:**
- Create: `bookings/notifications.py`
- Create: `bookings/tests/test_notifications.py`

**Interfaces:**
- Produces: `notify(booking, event)` function.

- [ ] **Step 1: Write failing test in `bookings/tests/test_notifications.py`**

Create `bookings/tests/test_notifications.py`:

```python
from django.test import TestCase, override_settings
from django.core import mail
from accounts.models import User
from tenants.models import Tenant
from bookings.models import StaffProfile, EventType, BookingRequest
from bookings.notifications import notify
from django.utils import timezone


class NotificationTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name='Test Tenant', slug='test')
        self.user = User.objects.create_user(
            email='staff@test.com',
            password='test',
            role=User.Role.TENANT_STAFF,
            tenant=self.tenant,
        )
        self.profile = StaffProfile.objects.create(user=self.user, tenant=self.tenant)
        self.event_type = EventType.objects.create(
            tenant=self.tenant,
            name='Intro Call',
            slug='intro-call',
            duration_minutes=30,
            assigned_staff=self.profile,
        )
        self.booking = BookingRequest.objects.create(
            tenant=self.tenant,
            event_type=self.event_type,
            staff=self.profile,
            status=BookingRequest.Status.PENDING,
            start_at=timezone.now() + timezone.timedelta(days=1),
            end_at=timezone.now() + timezone.timedelta(days=1, hours=1),
            booker_name='Test Booker',
            booker_email='booker@test.com',
        )

    def test_notify_sends_email(self):
        notify(self.booking, 'booking.approved')
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('Test Tenant', mail.outbox[0].subject)

    @override_settings(BOOKING_NOTIFICATIONS_ENABLED=False)
    def test_notify_disabled(self):
        notify(self.booking, 'booking.approved')
        self.assertEqual(len(mail.outbox), 0)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python manage.py test bookings.tests.test_notifications -v 2`
Expected: FAIL — `bookings.notifications` not defined.

- [ ] **Step 3: Create `bookings/notifications.py`**

```python
from django.conf import settings
from django.core.mail import send_mail


def _render(event, booking):
    subjects = {
        'booking.created': f'Booking request received - {booking.tenant.name}',
        'booking.approved': f'Booking confirmed - {booking.event_type.name}',
        'booking.rejected': f'Booking request declined - {booking.event_type.name}',
        'booking.canceled': f'Booking canceled - {booking.event_type.name}',
        'booking.completed': f'Booking completed - {booking.event_type.name}',
        'payment.succeeded': f'Payment received - {booking.event_type.name}',
    }
    subject = subjects.get(event, f'Booking update - {booking.event_type.name}')
    body = f'Your booking {booking.booking_ref} has been updated: {event}'
    return subject, body


def notify(booking, event):
    if not getattr(settings, 'BOOKING_NOTIFICATIONS_ENABLED', True):
        return
    subject, body = _render(event, booking)
    send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [booking.booker_email])
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python manage.py test bookings.tests.test_notifications -v 2`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add bookings/notifications.py bookings/tests/test_notifications.py
git commit -m "feat: add notify() for booking email notifications"
```

---

### Task 11: Build public booking views and templates

**Files:**
- Create: `bookings/urls.py`
- Create: `bookings/views.py` (partial — public views)
- Create: `bookings/forms.py` (partial — booking form)
- Create: `bookings/templates/bookings/tenant_home.html`
- Create: `bookings/templates/bookings/booking_create.html`
- Create: `bookings/templates/bookings/booking_success.html`
- Modify: `config/urls.py`

**Interfaces:**
- Produces: `/t/<slug>/`, `/t/<slug>/book/<event_type_slug>/`, `/t/<slug>/book/<event_type_slug>/success/<booking_ref>/`.

- [ ] **Step 1: Create `bookings/urls.py`**

```python
from django.urls import path
from bookings import views

app_name = 'bookings'

urlpatterns = [
    path('', views.TenantHomeView.as_view(), name='tenant_home'),
    path('book/<slug:event_type_slug>/', views.BookingCreateView.as_view(), name='booking_create'),
    path('book/<slug:event_type_slug>/success/<str:booking_ref>/', views.BookingSuccessView.as_view(), name='booking_success'),
]
```

- [ ] **Step 2: Create `bookings/views.py` with public views**

```python
from django.shortcuts import render, get_object_or_404, redirect
from django.views import View
from django.contrib import messages
from bookings.models import EventType, BookingRequest
from bookings.slots import compute_available_slots
from bookings.forms import BookingForm
from datetime import date


class TenantHomeView(View):
    def get(self, request, tenant_slug):
        event_types = EventType.objects.for_request(request).filter(is_active=True)
        return render(request, 'bookings/tenant_home.html', {'event_types': event_types})


class BookingCreateView(View):
    def get(self, request, tenant_slug, event_type_slug):
        event_type = get_object_or_404(EventType, slug=event_type_slug, tenant=request.tenant)
        selected_date = request.GET.get('date')
        slots = []
        if selected_date:
            slots = compute_available_slots(event_type, event_type.assigned_staff, date.fromisoformat(selected_date))
        form = BookingForm(event_type=event_type)
        return render(request, 'bookings/booking_create.html', {
            'event_type': event_type,
            'slots': slots,
            'selected_date': selected_date,
            'form': form,
        })

    def post(self, request, tenant_slug, event_type_slug):
        event_type = get_object_or_404(EventType, slug=event_type_slug, tenant=request.tenant)
        form = BookingForm(request.POST, event_type=event_type)
        if form.is_valid():
            booking = form.save(commit=False)
            booking.tenant = request.tenant
            booking.event_type = event_type
            booking.staff = event_type.assigned_staff
            booking.price_amount = event_type.price_amount
            booking.currency = event_type.currency
            booking.payment_mode = event_type.payment_mode
            booking.save()
            # Set initial status
            booking.status = BookingRequest.Status.PENDING if event_type.approval_required else BookingRequest.Status.APPROVED
            booking.save()
            from bookings.notifications import notify
            notify(booking, 'booking.created')
            return redirect('bookings:booking_success', tenant_slug=tenant_slug, event_type_slug=event_type_slug, booking_ref=booking.booking_ref)
        return render(request, 'bookings/booking_create.html', {
            'event_type': event_type,
            'form': form,
        })


class BookingSuccessView(View):
    def get(self, request, tenant_slug, event_type_slug, booking_ref):
        booking = get_object_or_404(BookingRequest, booking_ref=booking_ref, tenant=request.tenant)
        return render(request, 'bookings/booking_success.html', {'booking': booking})
```

- [ ] **Step 3: Create `bookings/forms.py`**

```python
from django import forms
from bookings.models import BookingRequest


class BookingForm(forms.ModelForm):
    class Meta:
        model = BookingRequest
        fields = ['start_at', 'booker_name', 'booker_email', 'booker_notes']
        widgets = {
            'start_at': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        }
```

- [ ] **Step 4: Create `bookings/templates/bookings/tenant_home.html`**

```html
{% extends "base.html" %}

{% block title %}{{ tenant.name }} - Book an Appointment{% endblock %}

{% block content %}
<section class="container mx-auto px-6 py-12">
  <h1 class="font-serif text-4xl text-deep-sage mb-8">Book with {{ tenant.name }}</h1>
  <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
    {% for event_type in event_types %}
    <a href="{% url 'bookings:booking_create' tenant.slug event_type.slug %}" class="block p-6 bg-white rounded-lg shadow hover:shadow-md transition">
      <h2 class="font-serif text-2xl text-deep-sage mb-2">{{ event_type.name }}</h2>
      <p class="text-charcoal mb-4">{{ event_type.description|truncatewords:20 }}</p>
      <div class="flex items-center text-sm text-charcoal/70">
        <span class="mr-4">{{ event_type.duration_minutes }} min</span>
        {% if event_type.price_amount > 0 %}
        <span>${{ event_type.price_amount }}</span>
        {% else %}
        <span>Free</span>
        {% endif %}
      </div>
    </a>
    {% empty %}
    <p class="text-charcoal">No event types available.</p>
    {% endfor %}
  </div>
</section>
{% endblock %}
```

- [ ] **Step 5: Create `bookings/templates/bookings/booking_create.html`**

```html
{% extends "base.html" %}

{% block title %}Book {{ event_type.name }} - {{ tenant.name }}{% endblock %}

{% block content %}
<section class="container mx-auto px-6 py-12 max-w-2xl">
  <h1 class="font-serif text-4xl text-deep-sage mb-4">Book {{ event_type.name }}</h1>
  <p class="text-charcoal mb-8">{{ event_type.description }}</p>

  <form method="post" class="space-y-6">
    {% csrf_token %}
    <div>
      <label class="block text-charcoal font-medium mb-2">Date & Time</label>
      <input type="date" name="date" value="{{ selected_date }}" class="tf-input" onchange="this.form.submit()">
    </div>

    {% if slots %}
    <div>
      <label class="block text-charcoal font-medium mb-2">Available Slots</label>
      <div class="grid grid-cols-3 gap-2">
        {% for slot in slots %}
        <label class="block">
          <input type="radio" name="start_at" value="{{ slot.isoformat }}" class="hidden peer" required>
          <div class="p-3 text-center border rounded-lg peer-checked:border-deep-sage peer-checked:bg-deep-sage/10 cursor-pointer">
            {{ slot|time:"H:i" }}
          </div>
        </label>
        {% endfor %}
      </div>
    </div>
    {% endif %}

    <div>
      <label class="block text-charcoal font-medium mb-2">Your Name</label>
      {{ form.booker_name }}
    </div>

    <div>
      <label class="block text-charcoal font-medium mb-2">Your Email</label>
      {{ form.booker_email }}
    </div>

    <div>
      <label class="block text-charcoal font-medium mb-2">Notes (optional)</label>
      {{ form.booker_notes }}
    </div>

    <button type="submit" class="px-6 py-3 bg-deep-sage text-white rounded-lg hover:bg-deep-sage/90">
      Request Booking
    </button>
  </form>
</section>
{% endblock %}
```

- [ ] **Step 6: Create `bookings/templates/bookings/booking_success.html`**

```html
{% extends "base.html" %}

{% block title %}Booking Confirmed - {{ tenant.name }}{% endblock %}

{% block content %}
<section class="container mx-auto px-6 py-12 max-w-2xl text-center">
  <h1 class="font-serif text-4xl text-deep-sage mb-4">Booking Request Received</h1>
  <p class="text-charcoal mb-8">Your booking reference is <strong>{{ booking.booking_ref }}</strong>.</p>
  <p class="text-charcoal">We will review your request and send a confirmation email shortly.</p>
</section>
{% endblock %}
```

- [ ] **Step 7: Wire bookings URLs in `config/urls.py`**

```python
from bookings.urls import urlpatterns as bookings_urls

urlpatterns = [
    path('', home, name='home'),
    path('t/<slug:tenant_slug>/', include(bookings_urls)),
    path('accounts/', include('two_factor.urls', namespace='two_factor')),
    path('admin/', admin.site.urls),
]
```

- [ ] **Step 8: Test public booking flow**

Run: `.venv/bin/python manage.py shell -c "
from django.test import Client
from tenants.models import Tenant
from bookings.models import EventType, StaffProfile
from accounts.models import User

t = Tenant.objects.create(name='Test', slug='test')
u = User.objects.create_user(email='staff@test.com', password='test', role='tenant_staff', tenant=t)
p = StaffProfile.objects.get(user=u)
et = EventType.objects.create(tenant=t, name='Test', slug='test', duration_minutes=30, assigned_staff=p)

c = Client()
r = c.get('/t/test/', HTTP_HOST='127.0.0.1')
print('tenant home:', r.status_code)
r = c.get('/t/test/book/test/', HTTP_HOST='127.0.0.1')
print('booking create:', r.status_code)
"
Expected: `tenant home: 200`, `booking create: 200`.

- [ ] **Step 9: Commit**

```bash
git add bookings/urls.py bookings/views.py bookings/forms.py bookings/templates/bookings/ config/urls.py
git commit -m "feat: add public booking views and templates"
```

---

### Task 12: Build staff dashboard views and templates

**Files:**
- Create: `bookings/views.py` (extend — staff views)
- Create: `bookings/urls.py` (extend — staff URLs)
- Create: `bookings/templates/bookings/staff_dashboard.html`
- Create: `bookings/templates/bookings/booking_detail.html`

**Interfaces:**
- Produces: `/t/<slug>/staff/`, `/t/<slug>/staff/bookings/<booking_ref>/`, action views.

- [ ] **Step 1: Add staff views to `bookings/views.py`**

```python
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.http import PermissionDenied


def tenant_staff_required(view):
    @method_decorator(login_required(login_url='/accounts/login/'))
    def wrapper(request, *args, **kwargs):
        if request.user.role not in ('tenant_admin', 'tenant_staff'):
            raise PermissionDenied
        if request.user.tenant_id != request.tenant.id:
            raise PermissionDenied
        return view(request, *args, **kwargs)
    return wrapper


@method_decorator(tenant_staff_required, name='dispatch')
class StaffDashboardView(View):
    def get(self, request, tenant_slug):
        bookings = BookingRequest.objects.for_request(request)
        grouped = {
            'pending': bookings.filter(status=BookingRequest.Status.PENDING),
            'awaiting_payment': bookings.filter(status=BookingRequest.Status.AWAITING_PAYMENT),
            'approved': bookings.filter(status=BookingRequest.Status.APPROVED),
            'completed': bookings.filter(status=BookingRequest.Status.COMPLETED),
        }
        return render(request, 'bookings/staff_dashboard.html', {'grouped': grouped})


@method_decorator(tenant_staff_required, name='dispatch')
class BookingDetailView(View):
    def get(self, request, tenant_slug, booking_ref):
        booking = get_object_or_404(BookingRequest, booking_ref=booking_ref, tenant=request.tenant)
        return render(request, 'bookings/booking_detail.html', {'booking': booking})


@method_decorator(tenant_staff_required, name='dispatch')
class BookingApproveView(View):
    def post(self, request, tenant_slug, booking_ref):
        booking = get_object_or_404(BookingRequest, booking_ref=booking_ref, tenant=request.tenant)
        booking.approve()
        messages.success(request, 'Booking approved.')
        return redirect('bookings:booking_detail', tenant_slug=tenant_slug, booking_ref=booking_ref)


@method_decorator(tenant_staff_required, name='dispatch')
class BookingRejectView(View):
    def post(self, request, tenant_slug, booking_ref):
        booking = get_object_or_404(BookingRequest, booking_ref=booking_ref, tenant=request.tenant)
        booking.reject()
        messages.success(request, 'Booking rejected.')
        return redirect('bookings:booking_detail', tenant_slug=tenant_slug, booking_ref=booking_ref)


@method_decorator(tenant_staff_required, name='dispatch')
class BookingCancelView(View):
    def post(self, request, tenant_slug, booking_ref):
        booking = get_object_or_404(BookingRequest, booking_ref=booking_ref, tenant=request.tenant)
        booking.cancel()
        messages.success(request, 'Booking canceled.')
        return redirect('bookings:booking_detail', tenant_slug=tenant_slug, booking_ref=booking_ref)


@method_decorator(tenant_staff_required, name='dispatch')
class BookingCompleteView(View):
    def post(self, request, tenant_slug, booking_ref):
        booking = get_object_or_404(BookingRequest, booking_ref=booking_ref, tenant=request.tenant)
        booking.mark_completed()
        messages.success(request, 'Booking marked completed.')
        return redirect('bookings:booking_detail', tenant_slug=tenant_slug, booking_ref=booking_ref)
```

- [ ] **Step 2: Add staff URLs to `bookings/urls.py`**

```python
urlpatterns += [
    path('staff/', views.StaffDashboardView.as_view(), name='staff_dashboard'),
    path('staff/bookings/<str:booking_ref>/', views.BookingDetailView.as_view(), name='booking_detail'),
    path('staff/bookings/<str:booking_ref>/approve/', views.BookingApproveView.as_view(), name='booking_approve'),
    path('staff/bookings/<str:booking_ref>/reject/', views.BookingRejectView.as_view(), name='booking_reject'),
    path('staff/bookings/<str:booking_ref>/cancel/', views.BookingCancelView.as_view(), name='booking_cancel'),
    path('staff/bookings/<str:booking_ref>/complete/', views.BookingCompleteView.as_view(), name='booking_complete'),
]
```

- [ ] **Step 3: Create `bookings/templates/bookings/staff_dashboard.html`**

```html
{% extends "base.html" %}

{% block title %}Staff Dashboard - {{ tenant.name }}{% endblock %}

{% block content %}
<section class="container mx-auto px-6 py-12">
  <h1 class="font-serif text-4xl text-deep-sage mb-8">Staff Dashboard</h1>

  {% for status, bookings in grouped.items %}
  <div class="mb-8">
    <h2 class="font-serif text-2xl text-deep-sage mb-4 capitalize">{{ status|replace:"_"," " }} ({{ bookings.count }})</h2>
    <div class="bg-white rounded-lg shadow overflow-hidden">
      <table class="w-full">
        <thead class="bg-pale-cream">
          <tr>
            <th class="px-6 py-3 text-left text-charcoal">Booking</th>
            <th class="px-6 py-3 text-left text-charcoal">Event Type</th>
            <th class="px-6 py-3 text-left text-charcoal">Date & Time</th>
            <th class="px-6 py-3 text-left text-charcoal">Booker</th>
            <th class="px-6 py-3 text-left text-charcoal">Actions</th>
          </tr>
        </thead>
        <tbody>
          {% for booking in bookings %}
          <tr class="border-t">
            <td class="px-6 py-4">{{ booking.booking_ref }}</td>
            <td class="px-6 py-4">{{ booking.event_type.name }}</td>
            <td class="px-6 py-4">{{ booking.start_at|date:"M d, Y H:i" }}</td>
            <td class="px-6 py-4">{{ booking.booker_name }}</td>
            <td class="px-6 py-4">
              <a href="{% url 'bookings:booking_detail' tenant.slug booking.booking_ref %}" class="text-terracotta hover:underline">View</a>
            </td>
          </tr>
          {% empty %}
          <tr class="border-t">
            <td colspan="5" class="px-6 py-4 text-charcoal/70">No bookings.</td>
          </tr>
          {% endfor %}
        </tbody>
      </table>
    </div>
  </div>
  {% endfor %}
</section>
{% endblock %}
```

- [ ] **Step 4: Create `bookings/templates/bookings/booking_detail.html`**

```html
{% extends "base.html" %}

{% block title %}Booking {{ booking.booking_ref }} - {{ tenant.name }}{% endblock %}

{% block content %}
<section class="container mx-auto px-6 py-12 max-w-3xl">
  <h1 class="font-serif text-4xl text-deep-sage mb-8">Booking {{ booking.booking_ref }}</h1>

  <div class="bg-white rounded-lg shadow p-6 mb-6">
    <div class="grid grid-cols-2 gap-4">
      <div>
        <dt class="text-charcoal/70 text-sm">Status</dt>
        <dd class="font-medium">{{ booking.get_status_display }}</dd>
      </div>
      <div>
        <dt class="text-charcoal/70 text-sm">Event Type</dt>
        <dd class="font-medium">{{ booking.event_type.name }}</dd>
      </div>
      <div>
        <dt class="text-charcoal/70 text-sm">Date & Time</dt>
        <dd class="font-medium">{{ booking.start_at|date:"M d, Y H:i" }}</dd>
      </div>
      <div>
        <dt class="text-charcoal/70 text-sm">Booker</dt>
        <dd class="font-medium">{{ booking.booker_name }} ({{ booking.booker_email }})</dd>
      </div>
    </div>
  </div>

  <div class="flex gap-4">
    {% if booking.status == 'pending' %}
    <form method="post" action="{% url 'bookings:booking_approve' tenant.slug booking.booking_ref %}">
      {% csrf_token %}
      <button type="submit" class="px-6 py-3 bg-deep-sage text-white rounded-lg hover:bg-deep-sage/90">Approve</button>
    </form>
    <form method="post" action="{% url 'bookings:booking_reject' tenant.slug booking.booking_ref %}">
      {% csrf_token %}
      <button type="submit" class="px-6 py-3 bg-terracotta text-white rounded-lg hover:bg-terracotta/90">Reject</button>
    </form>
    {% endif %}
    {% if booking.status == 'approved' %}
    <form method="post" action="{% url 'bookings:booking_cancel' tenant.slug booking.booking_ref %}">
      {% csrf_token %}
      <button type="submit" class="px-6 py-3 bg-charcoal text-white rounded-lg hover:bg-charcoal/90">Cancel</button>
    </form>
    <form method="post" action="{% url 'bookings:booking_complete' tenant.slug booking.booking_ref %}">
      {% csrf_token %}
      <button type="submit" class="px-6 py-3 bg-deep-sage text-white rounded-lg hover:bg-deep-sage/90">Mark Completed</button>
    </form>
    {% endif %}
  </div>
</section>
{% endblock %}
```

- [ ] **Step 5: Test staff dashboard access control**

Run: `.venv/bin/python manage.py shell -c "
from django.test import Client
from accounts.models import User
from tenants.models import Tenant

t = Tenant.objects.get(slug='test')
c = Client()

# Test tenant_staff access
u = User.objects.get(email='staff@test.com')
c.force_login(u)
r = c.get('/t/test/staff/', HTTP_HOST='127.0.0.1')
print('staff dashboard (tenant_staff):', r.status_code)

# Test platform_admin denied
pa = User.objects.create_superuser(email='pa@test.com', password='test', role='platform_admin')
c.force_login(pa)
r = c.get('/t/test/staff/', HTTP_HOST='127.0.0.1')
print('staff dashboard (platform_admin):', r.status_code)
"
Expected: `staff dashboard (tenant_staff): 200`, `staff dashboard (platform_admin): 403`.

- [ ] **Step 6: Commit**

```bash
git add bookings/views.py bookings/urls.py bookings/templates/bookings/staff_dashboard.html bookings/templates/bookings/booking_detail.html
git commit -m "feat: add staff dashboard and booking detail views"
```

---

### Task 13: Build tenant config views (EventType CRUD, StaffProfile edit, TimeOff CRUD, Tenant settings)

**Files:**
- Create: `bookings/views.py` (extend — config views)
- Create: `bookings/urls.py` (extend — config URLs)
- Create: `bookings/forms.py` (extend — config forms)
- Create: templates for config pages

This task is large. I'll break it into sub-tasks in the implementation, but for the plan, I'll outline the structure:

- `EventTypeListView`, `EventTypeCreateView`, `EventTypeUpdateView`, `EventTypeDeleteView` (tenant_admin only)
- `StaffProfileSelfEditView` (tenant_admin + tenant_staff, own profile only)
- `StaffTimeOffListView`, `StaffTimeOffCreateView`, `StaffTimeOffDeleteView` (tenant_admin + tenant_staff, own time-off only)
- `TenantSettingsView` (tenant_admin only)

Each follows the same pattern as the staff dashboard views with `tenant_admin_required` or `tenant_staff_required` decorator.

Given the size, I'll implement these in the execution phase with the same TDD pattern. The templates will follow the Tailwind styling established in the public and staff views.

- [ ] **Step 1: Add config views to `bookings/views.py`** (to be implemented)
- [ ] **Step 2: Add config URLs to `bookings/urls.py`** (to be implemented)
- [ ] **Step 3: Add config forms to `bookings/forms.py`** (to be implemented)
- [ ] **Step 4: Create config templates** (to be implemented)
- [ ] **Step 5: Test config views** (to be implemented)
- [ ] **Step 6: Commit** (to be implemented)

---

### Task 14: Build Unfold admin registration

**Files:**
- Create: `bookings/admin.py`

**Interfaces:**
- Produces: Unfold admin for `StaffProfile`, `EventType`, `BookingRequest`, `StaffTimeOff` (platform-admin-only).

- [ ] **Step 1: Create `bookings/admin.py`**

```python
from django.contrib import admin
from unfold.admin import ModelAdmin
from bookings.models import StaffProfile, EventType, BookingRequest, StaffTimeOff


@admin.register(StaffProfile)
class StaffProfileAdmin(ModelAdmin):
    list_display = ('user', 'tenant', 'is_active', 'created_at')
    list_filter = ('is_active', 'tenant')
    search_fields = ('user__email',)


@admin.register(EventType)
class EventTypeAdmin(ModelAdmin):
    list_display = ('name', 'tenant', 'duration_minutes', 'price_amount', 'is_active')
    list_filter = ('is_active', 'tenant')
    search_fields = ('name', 'slug')


@admin.register(BookingRequest)
class BookingRequestAdmin(ModelAdmin):
    list_display = ('booking_ref', 'tenant', 'event_type', 'status', 'start_at', 'booker_name')
    list_filter = ('status', 'tenant')
    search_fields = ('booking_ref', 'booker_name', 'booker_email')


@admin.register(StaffTimeOff)
class StaffTimeOffAdmin(ModelAdmin):
    list_display = ('staff', 'date', 'all_day', 'reason')
    list_filter = ('all_day', 'tenant')
```

- [ ] **Step 2: Test admin access**

Run: `.venv/bin/python manage.py shell -c "
from django.test import Client
from accounts.models import User

c = Client()
pa = User.objects.get(email='pa@test.com')
c.force_login(pa)
r = c.get('/admin/bookings/', HTTP_HOST='127.0.0.1')
print('bookings admin:', r.status_code)
"
Expected: `bookings admin: 200`.

- [ ] **Step 3: Commit**

```bash
git add bookings/admin.py
git commit -m "feat: add Unfold admin for bookings models"
```

---

### Task 15: Wire settings and run full verification

**Files:**
- Modify: `config/settings/base.py` (add `BOOKING_NOTIFICATIONS_ENABLED`, `DEFAULT_SLOT_PROVIDER`)

**Interfaces:**
- Produces: Final settings configuration.

- [ ] **Step 1: Add settings to `config/settings/base.py`**

```python
BOOKING_NOTIFICATIONS_ENABLED = env.bool('BOOKING_NOTIFICATIONS_ENABLED', default=True)
DEFAULT_SLOT_PROVIDER = env.str('DEFAULT_SLOT_PROVIDER', default='bookings.slots.WorkingHoursSlotProvider')
```

- [ ] **Step 2: Run full test suite**

Run: `.venv/bin/python manage.py test bookings accounts.tests tenants.tests -v 2`
Expected: all tests pass.

- [ ] **Step 3: Run `check`**

Run: `.venv/bin/python manage.py check`
Expected: passes with only `staticfiles.W004`.

- [ ] **Step 4: Run `migrate`**

Run: `.venv/bin/python manage.py migrate`
Expected: applies all migrations.

- [ ] **Step 5: Manual end-to-end verification**

1. Create a `tenant_admin` via shell -> verify `StaffProfile` auto-created with Mon-Fri 9-17 working hours.
2. Create an `EventType` via `/t/<slug>/staff/event-types/new/` -> verify it appears on `/t/<slug>/`.
3. Submit a booking as anonymous -> verify `BookingRequest` in `pending`, email in `mail.outbox`.
4. Approve via `/t/<slug>/staff/bookings/<ref>/approve/` -> verify status `approved`, email sent.
5. Block a date via `/t/<slug>/staff/time-off/new/` -> verify `compute_available_slots` excludes that date.
6. Log in as `platform_admin` -> verify all tenants' bookings visible in Unfold admin.
7. Log in as `tenant_staff` from a different tenant -> verify `/t/<other-slug>/staff/` returns 403.

- [ ] **Step 6: Commit**

```bash
git add config/settings/base.py
git commit -m "feat: add booking settings and complete wiring"
```

---

## Self-Review

1. **Spec coverage:** All sections covered — models (Tasks 4-7), state machine (Task 7), SlotProvider (Task 9), notifications (Task 10), public views (Task 11), staff dashboard (Task 12), config views (Task 13), admin (Task 14), settings (Task 15), auto-provision signal (Task 8).

2. **Placeholder scan:** Task 13 is outlined but not fully detailed. Will be completed during execution with the same TDD pattern.

3. **Type consistency:** All model field types, method signatures, and URL patterns match the spec. `BookingRequest.Status` choices match transition methods. `SlotProvider` protocol matches `WorkingHoursSlotProvider` implementation.

---

Plan complete and saved to `docs/superpowers/plans/2026-07-04-booking-core-implementation-plan.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
