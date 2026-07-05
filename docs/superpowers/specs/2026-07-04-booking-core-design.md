# Booking Core Milestone Design

**Date:** 2026-07-04
**Status:** Approved
**Scope:** Configurable event types, staff profiles with working hours and time-off, timezone-aware availability computation, the booking request state machine, a public booking page, a tenant-scoped staff approval dashboard with config pages, and email notifications on state transitions.

This milestone builds on the Foundation (auth, tenancy, 2FA admin, Tailwind UI) and delivers the core booking flow. Google Calendar integration (Milestone 3), Stripe Connect payments (Milestone 4), and webhooks/embed widget (Milestone 5) are out of scope.

---

## 1. Goals & Boundaries

### In scope

- `StaffProfile` model linking `User` to tenant-scheduling data + working hours JSON.
- Auto-provisioning: `post_save` signal on `accounts.User` creates a `StaffProfile` for every `tenant_admin`/`tenant_staff` with default Mon-Fri 09:00-17:00 working hours (solo-operator zero-setup).
- `StaffTimeOff` model for blocking specific dates (full or partial day).
- `EventType` model (duration, buffer, price, approval flag, location, assigned staff, intake fields JSON schema, cancellation policy).
- `BookingRequest` model with the full PRD state machine (`draft`, `pending`, `awaiting_payment`, `approved`, `rejected`, `canceled`, `completed`) and payment-mode fields (no Stripe flow).
- `SlotProvider` protocol + `WorkingHoursSlotProvider` implementation.
- Public booking page at `/t/<slug>/book/<event_type_slug>/` (anonymous).
- Staff dashboard at `/t/<slug>/staff/` (login + role + tenant guard).
- Tenant-config CRUD pages under `/t/<slug>/staff/` for `EventType`, `StaffProfile` self-edit, `StaffTimeOff`, and tenant settings.
- Sync email notifications via `notify(booking, event)`.
- `Tenant.timezone` field (default `UTC`).
- Unfold admin registration for new models (platform-admin-only).

### Out of scope

- Google Calendar/Meet integration (Milestone 3).
- Stripe Connect payment flow (Milestone 4) - payment fields exist; `awaiting_payment` reachable but inert.
- Outbound webhooks, embed widget, dashboards/reporting (Milestone 5).
- Reminder emails (require background scheduler).
- Background job queue.
- Booker accounts or email verification.

### Success criteria

1. `manage.py check` passes with only the expected `staticfiles.W004` warning.
2. `manage.py migrate` applies `bookings` migrations cleanly.
3. Creating a `tenant_admin` user automatically creates a `StaffProfile` with Mon-Fri 9-17 working hours (signal test).
4. State-machine unit tests prove every legal transition succeeds and every illegal transition raises `TransitionError`.
5. `WorkingHoursSlotProvider` tests prove availability correctly subtracts working-hour gaps, full-day time-off, and partial-day time-off.
6. A tenant admin can create an `EventType` and assign a staff member (themselves, by default) via the dashboard.
7. An anonymous booker can submit at `/t/<slug>/book/<event_type_slug>/` -> `BookingRequest` in `pending` (or `approved` if no approval required).
8. A logged-in `tenant_admin`/`tenant_staff` matching `request.tenant` can approve/reject from `/t/<slug>/staff/`; mismatched tenant denied (403).
9. Email notifications fire on `submit`, `approve`, `reject`, `cancel`, `mark_completed` (console backend in dev).
10. A `platform_admin` sees all tenants' bookings in Unfold admin; tenant users cannot access `/admin/`.

---

## 2. Visual References

The following screenshots in `docs/screenshots/` serve as visual guides for the dashboard and config UIs:

| Screenshot | Maps to |
|------------|---------|
| `dashboard.png` | `StaffDashboardView` - bookings grouped by status, pending approvals with approve/reject buttons |
| `event_types.png` | `EventTypeListView` - event type cards with duration, price, approval badge, active booking count |
| `availibility.png` | `StaffProfileSelfEditView` + `StaffTimeOff` - weekly schedule editor with day toggles, time pickers, buffer selector, unavailable dates section |
| `bookings.png` | `BookingDetailView` + approval actions - booking table with status badges, date filters, approve/reject actions |
| `settings.png` | `TenantSettingsView` - tenant name, timezone, branding configuration |

Implementation should match the layout, field structure, and styling shown in these screenshots.

---

## 3. App Structure

**One new Django app: `bookings`.** Registered in `INSTALLED_APPS` after `tenants`. All new models and views live here.

---

## 4. Data Model

### `tenants.Tenant` (modified)

| Field | Type | Notes |
|-------|------|-------|
| `timezone` | `CharField(max_length=64, default='UTC')` | IANA timezone name; used to interpret working hours |

### `bookings.StaffProfile` (inherits `tenants.TenantMixin`)

| Field | Type | Notes |
|-------|------|-------|
| `user` | `OneToOneField(accounts.User, on_delete=models.CASCADE)` | The linked user |
| `working_hours` | `JSONField(default=dict)` | `{0: [{"start":"09:00","end":"17:00"}], ...}` keyed by ISO weekday 0=Mon to 6=Sun; empty list = unavailable that day |
| `is_active` | `BooleanField(default=True)` | Soft-disable without deleting |
| `created_at` / `updated_at` | auto timestamps | |

- Default `working_hours` populated by the signal: Mon-Fri 09:00-17:00.
- Queryset inherits `TenantQuerySet` -> `StaffProfile.objects.for_request(request)`.

### `bookings.StaffTimeOff` (inherits `tenants.TenantMixin`)

| Field | Type | Notes |
|-------|------|-------|
| `staff` | `ForeignKey(StaffProfile, on_delete=models.CASCADE, related_name='time_off')` | |
| `date` | `DateField` | The calendar date being blocked |
| `all_day` | `BooleanField(default=True)` | If true, the whole working day is blocked |
| `start_time` | `TimeField(null=True, blank=True)` | Required when `all_day=False`; interpreted in tenant TZ |
| `end_time` | `TimeField(null=True, blank=True)` | Required when `all_day=False` |
| `reason` | `CharField(max_length=255, blank=True)` | Optional: "Vacation", "Lunch", etc. |
| `created_at` / `updated_at` | auto timestamps | |

- `unique_together = ('staff', 'date')` - one entry per staff per date.
- Validation: if `all_day=False`, both `start_time` and `end_time` required, and `start_time < end_time`.

### `bookings.EventType` (inherits `tenants.TenantMixin`)

| Field | Type | Notes |
|-------|------|-------|
| `name` | `CharField(max_length=255)` | |
| `slug` | `SlugField` | Unique within tenant (`unique_together = ('tenant', 'slug')`) |
| `description` | `TextField(blank=True)` | |
| `duration_minutes` | `PositiveIntegerField` | Event length |
| `buffer_minutes` | `PositiveIntegerField(default=0)` | Buffer before/after |
| `price_amount` | `DecimalField(max_digits=10, decimal_places=2, default=0)` | |
| `currency` | `CharField(max_length=3, default='USD')` | |
| `payment_mode` | `CharField(choices=no_payment/pay_at_request/pay_after_approval, default=no_payment)` | |
| `approval_required` | `BooleanField(default=True)` | If false, booking auto-approves on submit |
| `location` | `CharField(max_length=255, blank=True)` | Free text; Meet link filled in M3 |
| `assigned_staff` | `ForeignKey(StaffProfile, on_delete=models.PROTECT)` | Who the booking is with |
| `intake_fields` | `JSONField(default=list)` | List of `{name, label, type, required, choices}` |
| `cancellation_policy` | `TextField(blank=True)` | |
| `is_active` | `BooleanField(default=True)` | |
| `created_at` / `updated_at` | auto timestamps | |

### `bookings.BookingRequest` (inherits `tenants.TenantMixin`)

| Field | Type | Notes |
|-------|------|-------|
| `booking_ref` | `CharField(max_length=20, unique=True)` | Human-readable ID, e.g., `BKG-000123`, populated on creation |
| `event_type` | `ForeignKey(EventType, on_delete=models.PROTECT)` | |
| `staff` | `ForeignKey(StaffProfile, on_delete=models.PROTECT)` | Snapshotted from EventType at creation |
| `status` | `CharField(choices=Status, default=draft)` | State machine |
| `start_at` | `DateTimeField` | UTC, timezone-aware |
| `end_at` | `DateTimeField` | UTC, computed from start + duration + buffer |
| `booker_name` | `CharField(max_length=255)` | |
| `booker_email` | `EmailField` | |
| `booker_timezone` | `CharField(max_length=64, default='UTC')` | For display in emails |
| `booker_notes` | `TextField(blank=True)` | |
| `intake_responses` | `JSONField(default=dict)` | Keyed by intake field name |
| `price_amount` / `currency` / `payment_mode` | snapped from EventType | Snapshot at creation for audit |
| `payment_status` | `CharField(choices=unpaid/paid/refunded, default=unpaid)` | Stripe updates in M4 |
| `google_event_id` | `CharField(blank=True)` | M3 placeholder |
| `meet_url` | `URLField(blank=True)` | M3 placeholder |
| `created_at` / `updated_at` | auto timestamps | |

**`Status` choices:** `draft`, `pending`, `awaiting_payment`, `approved`, `rejected`, `canceled`, `completed`.

### Auto-provisioning signal

`accounts.signals.create_staff_profile_for_tenant_user` - `post_save` on `accounts.User`:
- If `instance.role in (TENANT_ADMIN, TENANT_STAFF)` and `instance.tenant is not None` and a `StaffProfile` for that user doesn't already exist -> create one with default Mon-Fri 9-17 working hours.
- Wired in `accounts.apps.AccountsConfig.ready()`.
- Idempotent: skip if profile exists (covers re-saves).

### Design rationale

- **`PROTECT` on `event_type`/`staff` FKs** - never accidentally delete a booking's referent.
- **Snapshot `price`/`currency`/`payment_mode` onto `BookingRequest`** - historical bookings don't change if EventType is edited later (audit integrity).
- **`staff` snapshotted on BookingRequest** - if EventType's assigned staff changes, existing bookings keep their original staff.
- **`working_hours` as JSON keyed by weekday** - simple, no extra model, easy for admin to edit via Unfold's JSON widget. Leaves room for a richer `WorkingHours` model later if overrides/time-off are needed.
- **`booking_ref` stored field** - makes URLs shareable and admin-friendly; formatted as `f"BKG-{id:06d}"` in a `pre_save` signal.

---

## 5. State Machine

### Transition table (legal moves only)

| From | Method | To | Guard | Side effect |
|------|--------|----|-------|-------------|
| `draft` | `submit()` | `pending` (if `approval_required`) or `approved` (if not) | must have `start_at`, `end_at`, `booker_email` | notify `booking.created` |
| `pending` | `approve()` | `awaiting_payment` (if `payment_mode == pay_after_approval`) or `approved` | - | notify `booking.approved` |
| `pending` | `reject()` | `rejected` | - | notify `booking.rejected` |
| `awaiting_payment` | `mark_paid()` | `approved` | `payment_status` set to `paid` first (by M4 Stripe webhook) | notify `payment.succeeded` |
| `approved` | `cancel()` | `canceled` | - | notify `booking.canceled` |
| `approved` | `mark_completed()` | `completed` | `start_at <= now` | notify `booking.completed` |
| `pending`/`awaiting_payment` | `cancel()` | `canceled` | - | notify `booking.canceled` |

**Illegal transitions raise `TransitionError`** (a custom `ValueError` subclass in `bookings.exceptions`). Examples: `approve()` from `approved`, `reject()` from `completed`, `submit()` from anything but `draft`.

### Note on `draft`

The public booking form in Booking Core is a single POST that creates `BookingRequest` directly in `pending`/`approved` (depending on `approval_required`). The `draft` state exists in the choices for forward-compat (save-and-resume in a later milestone) and to match the PRD table, but **no view creates `draft` records in this milestone**. The `submit()` method exists for the future draft->pending flow and is unit-tested in isolation.

### `notify()` integration

Each transition method, after committing the status change, calls `bookings.notifications.notify(booking, event_name)` where `event_name` is one of: `booking.created`, `booking.approved`, `booking.rejected`, `booking.canceled`, `booking.completed`, `payment.succeeded`.

---

## 6. Availability & SlotProvider

### `SlotProvider` protocol (in `bookings/slots.py`)

```python
from typing import NamedTuple, Protocol
from datetime import datetime

class BusyInterval(NamedTuple):
    start_at: datetime  # UTC, timezone-aware
    end_at: datetime    # UTC, timezone-aware
    source: str         # 'working_hours_gap' | 'time_off' | 'google' (M3)

class SlotProvider(Protocol):
    def compute_busy(
        self,
        staff: StaffProfile,
        start_at: datetime,
        end_at: datetime,
    ) -> list[BusyInterval]: ...
```

A `BusyInterval` is a span the staff member is **unavailable**. Availability is the complement: the requested window minus all busy intervals, minus the event's buffer.

### `WorkingHoursSlotProvider` (the only implementation in Booking Core)

`compute_busy(staff, start_at, end_at)`:

1. **Determine the date range** covered by `[start_at, end_at]` (UTC), converted to the tenant's timezone (`tenant.timezone`) to identify which calendar dates are relevant.
2. **For each date in range**, look up `staff.working_hours[weekday]`. If no entry or empty list -> the entire 24-hour span for that date (in tenant TZ) is busy (`source='working_hours_gap'`).
3. **For each working-hours entry** on a working day, the gap outside `[start_time, end_time]` (i.e., midnight->open and close->midnight in tenant TZ) is busy.
4. **Query `StaffTimeOff`** for `staff` where `date__in=[dates in range]`. Each `all_day` row -> busy covering the staff's working span that day. Each partial row -> busy `[date + start_time, date + end_time]` in tenant TZ. (`source='time_off'`.)
5. **Convert** all intervals to UTC, clamp to `[start_at, end_at]`, merge overlapping intervals, return sorted list.

### `compute_available_slots()` (the consumer-facing function)

```python
def compute_available_slots(
    event_type: EventType,
    staff: StaffProfile,
    date: date,
    granularity_minutes: int = 30,
) -> list[datetime]:
```

- Builds the requested window: `[date 00:00, date 23:59]` in tenant TZ -> UTC.
- Calls the registered provider's `compute_busy(staff, window_start, window_end)`.
- Subtracts busy intervals from the window, then splits the free spans into candidate start times at `granularity_minutes` increments (default 30).
- For each candidate start, checks that `[start, start + duration_minutes + 2*buffer_minutes]` fits entirely within one free span (buffer before and after).
- Returns the list of valid UTC `start_at` datetimes.

### Provider registration

A single `DEFAULT_SLOT_PROVIDER` setting (default `'bookings.slots.WorkingHoursSlotProvider'`). A `get_slot_provider()` factory returns an instance. M3 will register a composite provider that calls both `WorkingHoursSlotProvider` and `GoogleCalendarSlotProvider` and merges results. **No settings change needed in M3** - only the factory's default or a per-tenant override.

### Caching

None in this milestone. Availability is recomputed per request. The PRD lists "cached availability" as a non-functional concern; defer until a perf problem is measured.

---

## 7. URLs, Views & Access Control

### URL structure (added to `config/urls.py`)

All booking routes are tenant-scoped via the existing `TenantMiddleware` (which already resolves `/t/<slug>/`). New `bookings/urls.py` is included under `t/<slug>/`:

| Pattern | View | Auth | Purpose |
|---------|------|------|---------|
| `/t/<slug>/` | `TenantHomeView` | public | Lists tenant's active event types |
| `/t/<slug>/book/<event_type_slug>/` | `BookingCreateView` | public | Pick slot + fill intake form + submit |
| `/t/<slug>/book/<event_type_slug>/success/<str:booking_ref>/` | `BookingSuccessView` | public | Confirmation page |
| `/t/<slug>/staff/` | `StaffDashboardView` | login + role + tenant | Bookings grouped by status |
| `/t/<slug>/staff/bookings/<str:booking_ref>/` | `BookingDetailView` | login + role + tenant | Full booking context + actions |
| `/t/<slug>/staff/bookings/<str:booking_ref>/approve/` | `BookingApproveView` | login + role + tenant | POST: approve |
| `/t/<slug>/staff/bookings/<str:booking_ref>/reject/` | `BookingRejectView` | login + role + tenant | POST: reject |
| `/t/<slug>/staff/bookings/<str:booking_ref>/cancel/` | `BookingCancelView` | login + role + tenant | POST: cancel |
| `/t/<slug>/staff/bookings/<str:booking_ref>/complete/` | `BookingCompleteView` | login + role + tenant | POST: mark completed |
| `/t/<slug>/staff/event-types/` | `EventTypeListView` | tenant_admin | List event types |
| `/t/<slug>/staff/event-types/new/` | `EventTypeCreateView` | tenant_admin | Create |
| `/t/<slug>/staff/event-types/<int:pk>/edit/` | `EventTypeUpdateView` | tenant_admin | Edit |
| `/t/<slug>/staff/event-types/<int:pk>/delete/` | `EventTypeDeleteView` | tenant_admin | Delete (PROTECT if bookings exist) |
| `/t/<slug>/staff/profile/` | `StaffProfileSelfEditView` | tenant_admin, tenant_staff | Edit own working hours |
| `/t/<slug>/staff/time-off/` | `StaffTimeOffListView` | tenant_admin, tenant_staff | List own time-off |
| `/t/<slug>/staff/time-off/new/` | `StaffTimeOffCreateView` | tenant_admin, tenant_staff | Create |
| `/t/<slug>/staff/time-off/<int:pk>/delete/` | `StaffTimeOffDeleteView` | tenant_admin, tenant_staff | Delete |
| `/t/<slug>/staff/settings/` | `TenantSettingsView` | tenant_admin | Edit tenant name, timezone, branding |

### Access control

**Public routes** (`TenantHomeView`, `BookingCreateView`, `BookingSuccessView`): no auth. The `TenantMiddleware` already sets `request.tenant`; views 404 if the tenant slug is unknown or inactive.

**Staff routes**: a single decorator `tenant_staff_required`:
```python
def tenant_staff_required(view):
    @login_required(login_url=reverse_lazy('two_factor:login'))
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        user = request.user
        if user.role not in (User.Role.TENANT_ADMIN, User.Role.TENANT_STAFF):
            raise PermissionDenied
        if user.tenant_id != request.tenant.id:
            raise PermissionDenied
        return view(request, *args, **kwargs)
    return wrapper
```

- Uses the already-wired `two_factor:login`.
- Enforces both role and tenant match.
- `BookingDetailView`/action views additionally verify `booking.tenant_id == request.user.tenant_id` (defense in depth).

**Config routes**: `tenant_admin_required` decorator (same pattern but tighter role check - only `TENANT_ADMIN`).

**Self-edit routes** (`profile`, `time-off`): available to both `tenant_admin` and `tenant_staff`, scoped to `request.user.staff_profile` (the auto-provisioned profile) - a staff user only edits their own.

### Views (brief)

- **`TenantHomeView`**: fetches `EventType.objects.for_request(request).filter(is_active=True)`, renders `bookings/tenant_home.html`.
- **`BookingCreateView`**: GET renders a two-step form on one page - (1) date picker + fetched slots via `compute_available_slots`, (2) intake form rendered from `event_type.intake_fields` schema. POST validates, creates `BookingRequest` in `pending` (or `approved` if `not approval_required`), calls `notify(booking, 'booking.created')`, redirects to success page.
- **`StaffDashboardView`**: fetches `BookingRequest.objects.for_request(request)` grouped by status (`pending`, `awaiting_payment`, `approved`, `completed`), renders `bookings/staff_dashboard.html`.
- **`BookingDetailView`**: shows full booking; renders approve/reject/cancel/complete buttons depending on current status.
- **Action views**: POST-only, call the model's transition method, redirect back to detail. GET -> 405.
- **Config views** (`EventType*`, `StaffProfileSelfEditView`, `StaffTimeOff*`, `TenantSettingsView`): standard CRUD with tenant scoping.

### Templates (in `bookings/templates/bookings/`, extend `theme/templates/base.html`)

| Template | Purpose |
|----------|---------|
| `bookings/tenant_home.html` | Event type list |
| `bookings/booking_create.html` | Slot picker + intake form |
| `bookings/booking_success.html` | Confirmation |
| `bookings/staff_dashboard.html` | Grouped bookings |
| `bookings/booking_detail.html` | Detail + action buttons |
| `bookings/event_type_list.html`, `_form.html`, `_confirm_delete.html` | EventType CRUD |
| `bookings/staff_profile_edit.html` | Working hours editor |
| `bookings/staff_time_off_list.html`, `_form.html`, `_confirm_delete.html` | Time-off CRUD |
| `bookings/tenant_settings.html` | Tenant settings |

All styled with Tailwind classes matching Foundation's palette (`bg-pale-cream`, `text-deep-sage`, `font-serif` for headings, etc.).

### Admin (Unfold)

- `StaffProfileAdmin`, `EventTypeAdmin`, `BookingRequestAdmin`, `StaffTimeOffAdmin` registered in `bookings/admin.py`.
- Django admin (`/admin/`) stays **platform_admin only** per Foundation's design.
- These admin classes are for platform oversight and support, with tenant-scoped queryset filtering built in.
- Tenant admins manage their event types/staff via the **staff dashboard** views, not admin.

---

## 8. Notifications

Sync email dispatch via a `notify(booking, event)` hook. No background queue, no third-party email service.

### `bookings/notifications.py`

```python
def notify(booking: BookingRequest, event: str) -> None:
    if not getattr(settings, 'BOOKING_NOTIFICATIONS_ENABLED', True):
        return
    subject, body = _render(event, booking)
    send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [booking.booker_email])
```

### Events & recipients

| Event | Recipient | Subject template |
|-------|-----------|-----------------|
| `booking.created` | booker | "Booking request received - {tenant.name}" |
| `booking.approved` | booker | "Booking confirmed - {event_type.name}" |
| `booking.rejected` | booker | "Booking request declined - {event_type.name}" |
| `booking.canceled` | booker | "Booking canceled - {event_type.name}" |
| `booking.completed` | booker | "Booking completed - {event_type.name}" |
| `payment.succeeded` | booker | "Payment received - {event_type.name}" |

- Bookings are tenant-scoped; the tenant name appears in subjects for brand consistency.
- No staff notifications in this milestone (the dashboard is the staff's inbox).
- No reminders (deferred).

### Email templates

One template per event, stored in `bookings/templates/bookings/emails/<event>.txt` and `<event>.html`. Plain-text fallback for clients that don't render HTML. All templates extend a shared base that includes the Sage Nine Creative palette (Deep Sage headings, Pale Cream background) via Tailwind classes.

### Integration points

Each state-machine transition method calls `notify()` after committing:
- `BookingRequest.submit()` -> `notify(self, 'booking.created')`
- `approve()` -> `notify(self, 'booking.approved')`
- `reject()` -> `notify(self, 'booking.rejected')`
- `cancel()` -> `notify(self, 'booking.canceled')`
- `mark_completed()` -> `notify(self, 'booking.completed')`
- `mark_paid()` -> `notify(self, 'payment.succeeded')`

---

## 9. Settings & Wiring Changes

### `config/settings/base.py`

**INSTALLED_APPS** - add `bookings` under the local apps section:
```python
    # Local apps
    'tailwind',
    'theme',
    'accounts',
    'tenants',
    'bookings',
```

**New settings:**
```python
BOOKING_NOTIFICATIONS_ENABLED = env.bool('BOOKING_NOTIFICATIONS_ENABLED', default=True)
DEFAULT_SLOT_PROVIDER = env.str('DEFAULT_SLOT_PROVIDER', default='bookings.slots.WorkingHoursSlotProvider')
```

### `config/urls.py`

Add the bookings URL include under the tenant path:
```python
from bookings.urls import urlpatterns as bookings_urls

urlpatterns = [
    path('', home, name='home'),
    path('t/<slug:tenant_slug>/', include(bookings_urls)),
    path('accounts/', include('two_factor.urls', namespace='two_factor')),
    path('admin/', admin.site.urls),
]
```

### `tenants/models.py` - add `timezone` field

```python
class Tenant(models.Model):
    ...
    timezone = models.CharField(max_length=64, default='UTC')  # IANA timezone name
    ...
```

### `accounts/apps.py` - wire the StaffProfile auto-provision signal

```python
class AccountsConfig(AppConfig):
    ...
    def ready(self):
        import accounts.signals  # noqa: F401
```

### `accounts/signals.py` - new file

```python
from django.db.models.signals import post_save
from django.dispatch import receiver
from accounts.models import User
from bookings.models import StaffProfile

@receiver(post_save, sender=User)
def create_staff_profile_for_tenant_user(sender, instance, **kwargs):
    if instance.role in (User.Role.TENANT_ADMIN, User.Role.TENANT_STAFF) and instance.tenant is not None:
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

---

## 10. Testing Strategy

### Test files

| File | Covers |
|------|--------|
| `bookings/tests/test_models.py` | `StaffProfile`, `EventType`, `BookingRequest` field validation, `booking_ref` generation, `TenantMixin` queryset filtering |
| `bookings/tests/test_state_machine.py` | Every legal transition (assert new status), every illegal transition (assert `TransitionError`), `notify()` called with correct event |
| `bookings/tests/test_slots.py` | `WorkingHoursSlotProvider.compute_busy` for working day, non-working day, partial time-off, full-day time-off, multi-date range, timezone conversion; `compute_available_slots` for buffer, time-off exclusion, empty availability |
| `bookings/tests/test_views.py` | Public booking page (anonymous submit -> `pending`), staff dashboard access control (role + tenant match/mismatch), action views (POST-only, transition methods called), config views (tenant_admin only) |
| `bookings/tests/test_notifications.py` | `notify()` dispatches `send_mail` correctly, respects `BOOKING_NOTIFICATIONS_ENABLED`, correct subject/body per event |
| `bookings/tests/test_signals.py` | Auto-provisioned `StaffProfile` on `tenant_admin`/`tenant_staff` creation, idempotent on re-save, not created for `platform_admin` |
| `accounts/tests.py` (extend) | Signal fires correctly from `accounts.User` save |
| `tenants/tests.py` (extend) | `TenantMiddleware` still works with new `/t/<slug>/staff/` paths (skip prefix check) |

### Verification commands (post-implementation)

```bash
.venv/bin/python manage.py check
.venv/bin/python manage.py migrate
.venv/bin/python manage.py test bookings accounts.tests tenants.tests -v 2
```

Expected: all tests pass, `check` shows only `staticfiles.W004`.

### Manual verification

1. Create a `tenant_admin` via shell -> verify `StaffProfile` auto-created with Mon-Fri 9-17 working hours.
2. Create an `EventType` via `/t/<slug>/staff/event-types/new/` -> verify it appears on `/t/<slug>/`.
3. Submit a booking as anonymous -> verify `BookingRequest` in `pending`, email in `mail.outbox`.
4. Approve via `/t/<slug>/staff/bookings/<ref>/approve/` -> verify status `approved`, email sent.
5. Block a date via `/t/<slug>/staff/time-off/new/` -> verify `compute_available_slots` excludes that date.
6. Log in as `platform_admin` -> verify all tenants' bookings visible in Unfold admin.
7. Log in as `tenant_staff` from a different tenant -> verify `/t/<other-slug>/staff/` returns 403.

---

## 11. File Structure Summary

| File | Responsibility |
|------|---------------|
| `bookings/__init__.py` | App init |
| `bookings/apps.py` | App config |
| `bookings/models.py` | `StaffProfile`, `EventType`, `BookingRequest`, `StaffTimeOff`, `BookingRequest.Status`, `TransitionError` |
| `bookings/admin.py` | Unfold admin for all models (platform-admin-only) |
| `bookings/urls.py` | All booking routes |
| `bookings/views.py` | All views (public + staff + config) |
| `bookings/forms.py` | Django forms for booking submission, event type CRUD, staff profile, time-off |
| `bookings/slots.py` | `SlotProvider` protocol, `WorkingHoursSlotProvider`, `compute_available_slots` |
| `bookings/notifications.py` | `notify(booking, event)` |
| `bookings/exceptions.py` | `TransitionError` |
| `bookings/templates/bookings/*.html` | All booking templates |
| `bookings/templates/bookings/emails/*.txt,*.html` | Email templates |
| `bookings/tests/test_*.py` | Test modules |
| `accounts/signals.py` | `create_staff_profile_for_tenant_user` |
| `accounts/apps.py` | Wire signal in `ready()` |
| `tenants/models.py` | Add `timezone` field to `Tenant` |
| `config/settings/base.py` | Add `bookings` to `INSTALLED_APPS`, add `BOOKING_NOTIFICATIONS_ENABLED`, `DEFAULT_SLOT_PROVIDER` |
| `config/urls.py` | Include `bookings.urls` under `/t/<slug>/` |

---

## 12. Open Questions / Deferred

- **Reminders:** deferred (require background scheduler).
- **Stripe payment flow:** deferred to M4; `awaiting_payment` state reachable but inert.
- **Google Calendar busy times:** deferred to M3; `SlotProvider` protocol ready for `GoogleCalendarSlotProvider`.
- **Embed widget:** deferred to M5; public booking page is the hosted version only.
- **Outbound webhooks:** deferred to M5.
- **Booking search/filter in dashboard:** basic status grouping in Booking Core; date range search deferred.
- **Multi-staff event types:** `EventType.assigned_staff` is a single FK. Multi-staff (round-robin or booker-chooses) deferred.
- **Cancellation policy enforcement:** `cancellation_policy` is a text field; automated enforcement (e.g., "no cancellations within 24h") deferred.

---

## 13. Self-Review

- **Placeholder scan:** no TBD/TODO. All sections include exact file paths, field types, and code snippets.
- **Internal consistency:** state machine transitions match notification events; SlotProvider protocol matches WorkingHoursSlotProvider implementation; URL patterns match view names; access control decorators match role requirements.
- **Scope check:** focused enough for a single implementation plan. All models are tightly coupled (booking depends on event type, event type depends on staff profile, availability depends on staff profile and time-off). One app is appropriate.
- **Ambiguity check:** `draft` state clarified as forward-compat only; `awaiting_payment` clarified as reachable but inert until M4; `booking_ref` format specified; `working_hours` JSON structure specified; `StaffTimeOff` unique constraint specified.

No additional tasks needed.
