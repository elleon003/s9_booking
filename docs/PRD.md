# Product Requirements Document: Multi-Tenant Booking Platform

## TL;DR

A Django-based multi-tenant booking platform aimed at agencies, service businesses, and white-label operators needing advanced scheduling, manual approval, robust payment processing, and versatile outbound integrations. Separates booking logic from presentation, providing control, extensibility, and standardization across client environments.

---

## Goals

### Business Goals

* Enable efficient multi-tenant scheduling for agencies and white-label businesses
* Reduce platform lock-in through external system integrations
* Support cost-effective, self-hosted deployment options
* Monetize via application fees on Stripe Connect transactions
* Enable tenants to embed branded booking forms directly on their own websites (in addition to hosted booking pages).

### User Goals

* Simple, trustworthy booking experience with approval visibility
* Flexibility in payment timing and event logistics
* Clear notifications and confirmations
* Robust admin control over schedules, payments, and integrations

### Non-Goals

* Building a full-featured CRM as part of MVP
* Implementing a proprietary calendar engine
* Supporting every payment provider (Stripe Connect only in MVP)
* Full two-way editing for downstream CRMs/website platforms
* Building complete accounting or invoicing features

---

## User Stories

**Platform Operator**

* As a Platform Operator, I want to onboard new tenants and monitor platform-wide metrics, so that I can manage and monetize my ecosystem.

**Tenant Admin**

* As a Tenant Admin, I want to configure event types, approval rules, integrations, and payments, so that my business processes work my way.
* As a Tenant Admin, I want visibility into pending, paid, and approved bookings, so that I can act quickly on customer requests.
* As a Tenant Admin, I want to connect Google and Stripe accounts, so that calendars and payment flows are integrated without manual work.
* As a Tenant Admin, I want to generate an embed code for my booking form, so that I can offer seamless scheduling experiences to my customers right from my business website.

**Tenant Staff**

* As Tenant Staff, I want to review, approve or reject bookings, so that my schedule stays predictable and manageable.
* As Tenant Staff, I want to open calendar/Meet links directly from bookings, so that I can host events seamlessly.

**Customer/Booker**

* As a Customer, I want to request a booking, receive updates, and pay when required, so that scheduling and payment are easy.
* As a Customer, I want to book directly from the business’s website without being redirected elsewhere.

---

## Functional Requirements

### 1\. Tenancy & Account Management (Critical)

* Multi-tenant system with strict data and configuration isolation (`tenant_id` on all relevant tables)
* Role-based access (platform_admin, tenant_admin, tenant_staff)
* Per-tenant branding, calendar, payments, feature toggles

### 2\. Event & Booking Management (Critical)

* Configurable event types (fields: name, slug, duration, buffer, price, currency, approval required, location, assigned staff, intake fields, cancellation policy)
* Compute availability (uses working hours, Google Calendar busy times, event buffers)
* Booking request form (contact info, event type, timing, location, intake, payment status)
* Manual approval queue with clearly defined booking states
* Provide a secure, easy-to-use embeddable booking widget (e.g., iFrame/JS) for integration into tenant websites; inherit tenant branding, support all booking/approval/payment states, and function responsively.
* Generate unique embed codes/snippets for each tenant or event type via the admin dashboard.

### 3\. Google Calendar & Meet Integration (Critical)

* Per-tenant and per-staff OAuth connection with encrypted token storage
* Read busy times (re-check slot at both request & approval)
* Placeholder calendar event created at request (metadata keying for traceability)
* Confirm/update event at approval
* Google Meet creation on approval for virtual events

### 4\. Payment Processing with Stripe Connect (Critical)

* Each tenant connects their own Stripe Express account
* Collects payment via Stripe for approved bookings, with platform fee logic via destination charges
* Payment state tracking (intent, session, charge, payout, refund, dispute)
* Admin UI surfaced onboarding/remediation status
* Configurable payment timing: pay-after-approval (default) and pay-at-request (alternative)
* Full/partial refund support, admin audit of payment events

### 5\. Outbound Integrations & Webhooks (Critical)

* Tenant-configurable outbound webhooks/API endpoints, event subscription per type
* HTTP method, URL, headers, payload mapping template
* Support retries (exponential backoff), idempotency, signed payloads, and delivery logs
* Delivery/retry logs and test/dry-run endpoints for integration setup
* Key events:
  * booking.created, booking.pending, booking.approved, booking.rejected, booking.canceled, booking.rescheduled, booking.completed
  * payment.requested, payment.succeeded, payment.refunded
  * contact.created, contact.updated

### 6\. Notifications (High)

* Email notifications for all major booking/payment statuses (user & admin)
* Reminders for upcoming bookings

### 7\. Admin & Reporting Dashboards (High)

* Dashboard: bookings by state, pending approvals, integration health, failed syncs, payment status

### 8\. Non-Functional

* Security: Encrypted tokens, strict RBAC, sensitive data in Stripe only. Embedding solution must prevent cross-tenant data leakage and protect booking data in all iframe/JS interactions.
* Performance: Indexed tables, cached availability, background job queues
* Reliability: Idempotent sync, dead-letter queues for failed integrations
* Compliance: Audit logs, reconciled payment and booking state

---

## Booking State Table

| State | Trigger | Next State | Notes |
| --- | --- | --- | --- |
| draft | Form started | pending | Unsubmitted booking |
| pending | Request submitted | awaiting_payment/approved/rejected | Awaiting manual action/payment |
| awaiting_payment | Approval given | approved/rejected | Pay-after-approval |
| approved | Payment received (if needed) | completed/canceled | Booking is confirmed |
| rejected | Rejected by admin | — | Notification sent, placeholder removed |
| canceled | Canceled by user/admin | — | Refunds processed if needed |

---

## Data Model (Excerpt)

| Model | Key Fields (AI-parsable) |
| --- | --- |
| Tenant | id, name, branding, config, integration keys |
| User | id, email, roles |
| StaffProfile | id, user_id, tenant_id, permissions |
| EventType | id, tenant_id, slug, name, duration, price, approval, config |
| BookingRequest | id, tenant_id, event_type_id, staff_id, status, start, end, payment_status, google_event_id, meet_url, timestamps |
| BookingPayment | id, booking_id, stripe_charge_id, payment_intent_id, fee, status, refund/dispute info |
| OutboundIntegrationEndpoint | id, tenant_id, endpoint, auth, mapping, active |
| AuditLog | id, actor_type, action, target_id, json_snapshot, timestamp |

---

## User Experience

* Tenants sign up and connect accounts (Google, Stripe)
* Configure branding, event types, staff, and integrations

Booker Journey

* Select event type
* Pick time (in local timezone, availability checks)
* Fill intake form
* See approval/payment requirements clearly
* Pay upfront or after approval (varies by event type)
* Receive confirmation, reminders, updates
* Booker can seamlessly book from any tenant website with the embedded form; Tenant Admin can generate/embed/preview booking widgets from the dashboard, customize simple branding options, and deploy easily.

Admin/Staff Journey

* Dashboard shows pending bookings, integration health
* Approve/reject bookings, with notifications to bookers
* Refund/reject as needed, audit all actions
* Tenant Admin can generate/embed/preview booking widgets from the dashboard, customize simple branding options, and deploy easily.

---

## Key Workflow Diagram (Text Reference)

1. Booker requests booking → Placeholder Google Calendar event created
2. Admin reviews → Approves/rejects
  * On approve: Slot re-checked, confirmation event updated, Google Meet link generated (if needed)
  * On payment required: Booker pays (timing per config)
  * On reject: Notification and event removal
3. Audit logs and integration endpoints updated asynchronously

---

## Success Metrics

| Metric | Description | How Measured |
| --- | --- | --- |
| Tenant Onboarding Success | % of tenants who self-connect Google & Stripe without manual help | Onboarding completion logs |
| Approval Workflow Coverage | % bookings fully processed (manual/automatic) without manual entry | Booking state history |
| Payment Routing Accuracy | % of paid bookings where funds route correctly | Stripe logs, booking audits |
| Webhook Delivery Success | % of events successfully delivered to integrations | Integration logs |
| Visibility of Errors | % of failed syncs/issues visible/admin-acknowledged | Audit & admin logs |

---

## Technical Considerations

* Use Django + Django Ninja for API endpoints
* PostgreSQL as DB, Redis for background jobs/caching/queueing
* Use structured event metadata for integration traceability
* Primary integration points: Google Calendar/Meet (API), Stripe Connect, webhooks/API endpoints to CRMs/automation
* Data privacy: OAuth tokens encrypted at rest, payment data minimal—Stripe handles sensitive info
* Scalability: Indexed queries by tenant_id/status/date, async for high-volume events
* Operational risk: Sync retries, dead-letter queues, idempotent delivery everywhere

---

## Milestones & Sequencing

| Phase | Duration | Team Size / Key Roles | Core Deliverables |
| --- | --- | --- | --- |
| Foundation | 1–2 weeks | Small team (1–2 ppl, all roles) | Django proj, multi-tenant auth, models, UI shell |
| Booking Core | 2 weeks | Small team | Booking flow, approval, notifications |
| Google Integration | 1 week | Small team | Google OAuth, calendar, Meet, placeholder logic |
| Payments | 1–2 weeks | Small team | Stripe Connect, payment UIs, fee logic, refunds |
| Integrations/Hardening | 1–2 weeks | Small team | Webhook/API, retries, audit/reporting, launch |

---

## Appendix: Field Reference & Event Schema Examples (AI Ready)

Booking Request Example—JSON Shape

Booking Request Example—JSON Shape

```
{   "id": "BKG-1234",   "tenant_id": "TEN-2024",   "event_type_id": 1,   "assigned_staff_id": 35,   "status": "pending",   "requested_start_at": "2024-06-20T13:00:00Z",   "booker_timezone": "US/Eastern",   "price_amount": 129.00,   "currency": "USD",   "payment_mode": "pay_later",   "approval_required": true,   "google_event_id": "evt_abcdefg",   "google_meet_url": null,   ... }
```

Each tenant can deploy their own booking flows via a simple embed code placed in any site builder, CMS, or custom website. Embedding supports full booking/approval/payment flows with tenant-specific branding and secure, isolated data context.

**Outbound Webhook Example—JSON Event Payload**

```json
{
  "event": "booking.approved",
  "tenant_id": "TEN-2024",
  "booking": {
    "id": "BKG-1234",
    "status": "approved",
    "confirmed_location": "123 Main St, Anytown",
    "google_event_id": "evt_abcdefg"
  },
  "contact": {
    "first_name": "Jane",
    "last_name": "Smith",
    "email": "jane@example.com"
  },
  "occurred_at": "2024-06-20T14:00:00Z"
}

```

---

**Document optimized for AI readability and parsing. All sections use explicit lists, structured tables, and standardized labels for field and state references. Examples provided for key entities and event payloads.**