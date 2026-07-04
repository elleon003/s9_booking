# Tailwind-First UI Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move public/base templates into the `theme` app, remove inline CSS, configure Tailwind v4 brand tokens, and establish `.env.example` as the committed environment template.

**Architecture:** Tailwind v4 configuration lives in `theme/static_src/src/styles.css` via `@theme`. The base template in `theme/templates/base.html` loads the compiled Tailwind CSS and Google Fonts. All public pages extend this base. The top-level `templates/` folder is removed; Django discovers templates via `APP_DIRS`.

**Tech Stack:** Django 6.0, django-tailwind v4, Tailwind CSS v4.

## Global Constraints

- Django virtualenv lives at `.venv/`; use `.venv/bin/python manage.py <cmd>`.
- Tailwind v4 configuration lives in CSS only — no `tailwind.config.js`.
- No inline `<style>` blocks. No hand-authored `.css` files outside of `theme/static_src/src/styles.css`.
- The expected `staticfiles.W004` warning must not be "fixed" by removing the setting.
- Brand colors: Deep Sage `#50665A`, Charcoal `#333333`, Terracotta `#CC7755`, Pale Cream `#F8F8F0`. Fonts: DM Sans and Lora.
- `.env.example` is committed; `.env` is local-only.

---

## File Structure

| File | Responsibility |
|------|--------------|
| `theme/static_src/src/styles.css` | Tailwind v4 entrypoint + brand `@theme` block |
| `theme/templates/base.html` | Base template using Tailwind classes |
| `theme/templates/home.html` | Home/landing placeholder extending base |
| `config/settings/base.py` | Remove top-level `templates/` from `DIRS` |
| `AGENTS.md` | Update `.env` setup note |
| `.env.example` | Committed environment template |
| `.env` | Local copy (already created by user) |

---

### Task 1: Configure Tailwind v4 brand tokens

**Files:**
- Modify: `theme/static_src/src/styles.css`

**Interfaces:**
- Produces: Tailwind utilities `bg-deep-sage`, `text-charcoal`, `font-sans`, etc.

- [ ] **Step 1: Update `theme/static_src/src/styles.css`**

```css
@import "tailwindcss";

@source "../../../**/*.{html,py,js}";

@theme {
  --color-deep-sage: #50665A;
  --color-charcoal: #333333;
  --color-terracotta: #CC7755;
  --color-pale-cream: #F8F8F0;

  --font-sans: 'DM Sans', ui-sans-serif, system-ui, sans-serif;
  --font-serif: 'Lora', ui-serif, Georgia, serif;
}
```

- [ ] **Step 2: Build Tailwind CSS**

Run: `.venv/bin/python manage.py tailwind build`
Expected: compiles `theme/static/css/dist/styles.css` without errors.

---

### Task 2: Replace `theme/templates/base.html`

**Files:**
- Modify: `theme/templates/base.html`

**Interfaces:**
- Consumes: Tailwind compiled CSS via `{% tailwind_css %}`.
- Produces: Base template with `title`, `extra_head`, `content` blocks.

- [ ] **Step 1: Write new `theme/templates/base.html`**

```html
{% load static tailwind_tags %}
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{% block title %}S9 Booking{% endblock %}</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;700&family=Lora:wght@400;500;700&display=swap" rel="stylesheet">
  {% tailwind_css %}
  {% block extra_head %}{% endblock %}
</head>
<body class="bg-pale-cream text-charcoal font-sans antialiased"
      data-tenant-slug="{{ tenant.slug|default:'' }}">
  <main class="min-h-screen">
    {% block content %}{% endblock %}
  </main>
</body>
</html>
```

- [ ] **Step 2: Remove inline CSS from anywhere**

Search the project for inline `<style>` blocks and ensure none remain in templates (except this refactor's target). None expected except the soon-to-be-deleted top-level `templates/base.html`.

---

### Task 3: Move and rewrite `home.html`

**Files:**
- Delete: `templates/base.html`
- Delete: `templates/home.html`
- Delete: `templates/` directory (if empty)
- Create: `theme/templates/home.html`

**Interfaces:**
- Consumes: `theme/templates/base.html` and `tenant` context.
- Produces: Styled home page.

- [ ] **Step 1: Create `theme/templates/home.html`**

```html
{% extends "base.html" %}

{% block title %}{% if tenant %}{{ tenant.name }} Booking{% else %}S9 Booking{% endif %}{% endblock %}

{% block content %}
  <section class="container mx-auto px-6 py-24 text-center">
    <h1 class="font-serif text-5xl md:text-6xl text-deep-sage mb-6">
      {% if tenant %}
        Welcome to {{ tenant.name }}
      {% else %}
        Welcome to S9 Booking
      {% endif %}
    </h1>
    <p class="text-xl md:text-2xl max-w-2xl mx-auto leading-relaxed">
      {% if tenant %}
        Book your appointment with {{ tenant.name }}.
      {% else %}
        Simple, trustworthy scheduling for service businesses and agencies.
      {% endif %}
    </p>
  </section>
{% endblock %}
```

- [ ] **Step 2: Delete the top-level templates folder**

Run:
```bash
rm -rf templates/
```

- [ ] **Step 3: Update `config/settings/base.py` to remove `DIRS` entry**

Change:
```python
            'DIRS': [BASE_DIR / 'templates'],
```
to:
```python
            'DIRS': [],
```

- [ ] **Step 4: Verify home page renders**

Run:
```bash
.venv/bin/python manage.py shell -c "
from django.test import Client
c = Client()
r = c.get('/', HTTP_HOST='127.0.0.1')
print(r.status_code, 'Welcome' in r.content.decode())
"
```
Expected: `200 True`.

---

### Task 4: Environment file documentation

**Files:**
- Modify: `AGENTS.md`

**Interfaces:**
- Produces: Updated dev setup instructions referencing `.env.example`.

- [ ] **Step 1: Update `AGENTS.md` environment section**

Replace the existing `.env` section with:

```markdown
## Environment

- Python virtualenv lives at `.venv/`. Use `.venv/bin/python manage.py <cmd>` (or activate `.venv` first). The global interpreter does not have Django installed.
- Env loading via `environs`: `base.py` calls `env = Env(); env.read_env()`, which auto-discovers `.env` by recursing up from the CWD. A `.env` file at the project root is **required even in dev** — `base.py` reads `SECRET_KEY` with no default before `dev.py`'s default applies.
- A committed `.env.example` is provided. Copy it to `.env` for local development:
  ```bash
  cp .env.example .env
  ```
  Then override `SECRET_KEY` and any other local values. Do not commit `.env`.
```

- [ ] **Step 2: Verify `.env.example` contents**

Ensure `.env.example` contains:

```text
SECRET_KEY=django-insecure-dev-key-change-me
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1,::1,s9booking.local,*.s9booking.local
BASE_HOST=s9booking.local
DEFAULT_FROM_EMAIL=dev@s9booking.local
```

---

### Task 5: Cross-reference the Foundation spec and plan

**Files:**
- Modify: `docs/superpowers/specs/2026-07-02-foundation-design.md`
- Modify: `docs/superpowers/plans/2026-07-02-foundation-implementation-plan.md`

**Interfaces:**
- Produces: Clear note that UI/template decisions are superseded by the refactor doc.

- [ ] **Step 1: Add superseding note to Foundation design spec**

Insert at the top of `docs/superpowers/specs/2026-07-02-foundation-design.md`, just under the title:

```markdown
> **Note:** UI, template location, Tailwind configuration, and `.env` handling decisions in this document are superseded by `docs/superpowers/specs/2026-07-03-tailwind-ui-refactor-design.md`.
```

- [ ] **Step 2: Add superseding note to Foundation implementation plan**

Insert at the top of `docs/superpowers/plans/2026-07-02-foundation-implementation-plan.md`, just under the title:

```markdown
> **Note:** Tasks related to `templates/base.html`, `templates/home.html`, inline CSS, and `.env` setup are superseded by `docs/superpowers/plans/2026-07-03-tailwind-ui-refactor-implementation-plan.md`.
```

---

## Self-Review

- **Spec coverage:**
  - Tailwind v4 brand tokens: Task 1.
  - Base template in theme app: Task 2.
  - Home template moved and styled with Tailwind: Task 3.
  - `.env.example` documentation: Task 4.
  - Foundation docs cross-referenced: Task 5.
- **Placeholder scan:** no TBD/TODO.
- **Type consistency:** Tailwind class names match `@theme` tokens.

No additional tasks needed.
