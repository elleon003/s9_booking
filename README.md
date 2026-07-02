# S9 Booking

A Django-based, multi-tenant booking platform built for agencies, service businesses, and white-label operators who need more than a basic scheduling link.

S9 Booking separates booking logic from presentation so you can control schedules, approvals, payments, and integrations under one roof — then embed a branded booking widget on any site you choose.

Originally built for [Sage Nine Creative](https://sageninecreative.com/) clients. The application code is open source under the Apache-2.0 license.

---

## What it does

- **Multi-tenant scheduling** — isolated tenants, roles, and branding so each business runs its own world.
- **Configurable event types** — duration, buffers, pricing, approval rules, intake fields, cancellation policies, assigned staff, and more.
- **Manual approval workflow** — bookings move through clear states (`draft` → `pending` → `awaiting_payment` / `approved` / `rejected` / `canceled`) with audit trails.
- **Google Calendar & Google Meet integration** — per-tenant and per-staff OAuth, busy-time checks, placeholder events, confirmed events, and auto-generated Meet links.
- **Stripe Connect payments** — each tenant connects their own Stripe Express account; platform fees are handled via destination charges. Supports pay-after-approval (default) and pay-at-request.
- **Embeddable booking widget** — a secure, responsive iframe/JS snippet tenants can drop into their own websites with their own branding.
- **Outbound webhooks & integrations** — tenant-configurable HTTP endpoints for booking and payment events, with retries, idempotency, signed payloads, and delivery logs.
- **Email notifications & reminders** — for bookers, staff, and admins at every major state change.
- **Admin dashboards** — built with [Django Unfold](https://unfoldadmin.com/) and [Tailwind CSS](https://tailwindcss.com/) for a modern, fast admin experience.

---

## Tech stack

| Layer | Choice |
| --- | --- |
| Backend | Django 6 |
| API | Django Ninja (planned) |
| Admin UI | Django Unfold + Tailwind CSS v4 |
| Database | SQLite in dev; PostgreSQL in production |
| Cache / queue | Redis + Celery (planned) |
| Payments | Stripe Connect |
| Calendar | Google Calendar API + Google Meet |
| Env config | `environs` |

---

## Quick start

### Prerequisites

- Python 3.12+
- Node.js + npm (for Tailwind builds)
- A virtualenv tool of your choice

### 1. Clone and set up the environment

```bash
git clone <repository-url>
cd s9_booking
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
```

### 2. Configure environment variables

Create a `.env` file at the project root. Minimum dev settings:

```env
SECRET_KEY=django-insecure-dev-key-change-me
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1,::1
INTERNAL_IPS=127.0.0.1,localhost
```

> **Note:** `base.py` reads `SECRET_KEY` before dev defaults apply, so a `.env` file is required even in development.

### 3. Install Tailwind and build CSS

```bash
python manage.py tailwind install
python manage.py tailwind build
```

For active development, run the watch server in a separate terminal:

```bash
python manage.py tailwind start
```

### 4. Run migrations and start the server

```bash
python manage.py migrate
python manage.py runserver
```

The admin interface is available at `http://127.0.0.1:8000/admin/`.

---

## Settings layout

Settings are split by environment:

| File | Purpose |
| --- | --- |
| `config/settings/base.py` | Shared settings, Unfold config, Tailwind config |
| `config/settings/dev.py` | SQLite, console email, browser reload, dev defaults |
| `config/settings/prod.py` | PostgreSQL via `DATABASE_URL`, SMTP, HTTPS/HSTS hardening |

Production requires:

```env
DJANGO_SETTINGS_MODULE=config.settings.prod
SECRET_KEY=<strong-secret>
DEBUG=False
ALLOWED_HOSTS=<your-domain>
DATABASE_URL=postgres://user:pass@host:port/db
EMAIL_HOST=
EMAIL_PORT=
EMAIL_USE_TLS=
EMAIL_HOST_USER=
EMAIL_HOST_PASSWORD=
```

---

## Project structure

```
s9_booking/
├── config/                  # Django project configuration
│   ├── settings/
│   │   ├── base.py          # Shared settings
│   │   ├── dev.py           # Development settings
│   │   └── prod.py          # Production settings
│   ├── urls.py              # URL routing
│   ├── wsgi.py
│   └── asgi.py
├── theme/                   # Tailwind v4 app and compiled assets
│   ├── static/css/dist/     # Compiled Tailwind output
│   ├── static_src/          # Tailwind source and PostCSS config
│   └── templates/
├── docs/
│   ├── PRD.md               # Product requirements document
│   └── sage-nine-creative-brand-guidelines.md
├── manage.py
├── requirements.txt         # Core dependencies
├── requirements-dev.txt     # Dev dependencies
└── .env                     # Local environment variables (not committed)
```

---

## Verification

Run Django’s built-in checks:

```bash
python manage.py check
```

Expect one standing warning: `staticfiles.W004` — the top-level `static/` directory in `STATICFILES_DIRS` does not exist yet. This is harmless and expected; do not remove the setting.

---

## Development notes

- **Unfold ordering:** `unfold` and its contrib packages must appear **before** `django.contrib.admin` in `INSTALLED_APPS`. They already do.
- **Tailwind v4:** Configuration lives in `theme/static_src/src/styles.css`. There is no `tailwind.config.js`.
- **Browser reload:** `django_browser_reload` is mounted at `__reload__/` in debug mode. `INTERNAL_IPS` is set in dev so live reload works.
- **No test suite yet:** This project does not currently have tests, linting, or type-checking configured. Contributions that add them are welcome.

---

## Roadmap

The project is currently a scaffolded Django 6 application with Tailwind v4 and Unfold admin. Upcoming milestones, drawn from the PRD:

1. **Foundation** — tenant model, RBAC, user/staff profiles, audit log base.
2. **Booking core** — event types, availability engine, booking request flow, approval queue, notifications.
3. **Google integration** — OAuth, busy-time checks, placeholder/confirmed events, Google Meet.
4. **Payments** — Stripe Connect Express onboarding, payment timing modes, refunds, fee tracking.
5. **Integrations & hardening** — outbound webhooks, retries, delivery logs, dashboards, embeddable widget.

---

## Contributing

We welcome issues, discussions, and pull requests. Because the project is early, opening an issue before a large change is the best way to avoid duplicate work.

### Areas where help is especially welcome

- Test suite setup (pytest or Django’s test runner)
- Linting and formatting configuration
- Documentation and deployment guides
- Docker / self-hosting examples
- The multi-tenant availability engine
- Stripe Connect and Google OAuth integrations

---

## License

Licensed under the Apache License, Version 2.0. See [LICENSE](./LICENSE) for the full text.

---

## About the name

**S9 Booking** is the operational product name used by Sage Nine Creative. The open-source software is the same codebase that powers their hosted booking service.

Built with strategic insight, clarity, and just enough wit — the same way Sage Nine Creative builds brands.
