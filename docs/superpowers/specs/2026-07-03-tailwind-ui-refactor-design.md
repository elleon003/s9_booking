# Foundation UI Refactor: Tailwind-First Design

**Date:** 2026-07-03  
**Status:** Approved  
**Scope:** Move all public/base templates into the `theme` app, remove inline CSS, configure Tailwind v4 with Sage Nine Creative brand tokens, and establish `.env.example` as the committed environment template.

This document revises the UI layer decisions originally captured in `2026-07-02-foundation-design.md`.

---

## 1. Guiding Principles

1. **Tailwind CSS v4 is the single source of styling truth** for all non-Unfold pages and embed chrome.
2. **No inline `<style>` blocks** and **no hand-authored `.css` files** outside of `theme/static_src/src/styles.css`.
3. **All base templates live in `theme/templates/`** so they are co-located with the Tailwind app that styles them.
4. **Brand colors and fonts are configured in CSS** using Tailwind v4's `@theme` block, not inline or in Unfold settings alone.
5. **`.env.example` is committed** as a documented environment template; the real `.env` is created locally and not committed.

---

## 2. Tailwind v4 Configuration

Tailwind v4 does not use `tailwind.config.js`. Configuration lives in CSS.

### File: `theme/static_src/src/styles.css`

Current contents:

```css
@import "tailwindcss";
@source "../../../**/*.{html,py,js}";
```

Revised contents:

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

This exposes utilities such as:
- `bg-deep-sage`, `text-deep-sage`, `border-deep-sage`
- `bg-pale-cream`, `text-charcoal`, `text-terracotta`
- `font-sans`, `font-serif`

After editing this file, run `.venv/bin/python manage.py tailwind build` to regenerate `theme/static/css/dist/styles.css`.

---

## 3. Base Template

### File: `theme/templates/base.html`

Replaces both the existing `theme/templates/base.html` and the temporary top-level `templates/base.html`.

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

Notes:
- `data-tenant-slug` is reserved for future embed/widget JavaScript.
- The Google Fonts link is the only allowed external stylesheet; it is loaded before the compiled Tailwind CSS so custom font stacks resolve correctly.

---

## 4. Home Page Template

### File: `theme/templates/home.html`

Moved from `templates/home.html`.

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

---

## 5. Settings Changes

### `config/settings/base.py`

- Remove `BASE_DIR / 'templates'` from `TEMPLATES[0]['DIRS']`.
- Keep `APP_DIRS = True` so `theme/templates/base.html` and `theme/templates/home.html` are discovered via the `theme` app.

The `DIRS` entry may be left empty or removed:

```python
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        ...
    },
]
```

### Unfold admin styling

Unfold continues to use its own `UNFOLD['STYLES']` referencing `static('css/dist/styles.css')` — the compiled Tailwind output. The brand colors defined in `UNFOLD['COLORS']` remain, but public pages no longer depend on Unfold's internal CSS.

---

## 6. Environment File Handling

### `.env.example`

Committed at project root. Contains documented required keys:

```text
SECRET_KEY=django-insecure-dev-key-change-me
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1,::1,s9booking.local,*.s9booking.local
BASE_HOST=s9booking.local
DEFAULT_FROM_EMAIL=dev@s9booking.local
```

### `.env`

Created locally by copying `.env.example` and overriding secrets as needed. Not committed.

```bash
cp .env.example .env
```

### Documentation update

`AGENTS.md` should note that `.env` is required in dev and can be created from `.env.example`.

---

## 7. Out-of-Scope

- No changes to the Unfold admin internal templates or admin CSS.
- No new public pages beyond the home placeholder.
- No JavaScript widget code yet; `data-tenant-slug` is a placeholder attribute.

---

## 8. Verification

After the refactor:

1. Run `.venv/bin/python manage.py tailwind build`.
2. Run `.venv/bin/python manage.py check` — expect only `staticfiles.W004`.
3. Run `.venv/bin/python manage.py test accounts.tests tenants.tests` — all tests pass.
4. Request `/` and `/t/sage-nine/` via the test client and confirm Tailwind classes render ( Deep Sage headings, Pale Cream background, DM Sans body, Lora headings).

---

## 9. Files Affected

| Action | File |
|--------|------|
| Update | `theme/static_src/src/styles.css` |
| Update | `theme/templates/base.html` |
| Move + update | `templates/home.html` → `theme/templates/home.html` |
| Delete | `templates/base.html` |
| Delete | `templates/` directory |
| Update | `config/settings/base.py` (remove `DIRS` entry) |
| Update | `AGENTS.md` (`.env.example` copy note) |
| Keep | `.env.example` committed |
| Create locally | `.env` from `.env.example` |

---

## 10. Open Questions / Future Decisions

- Should the embed widget use the same compiled `styles.css` or a separate, smaller build? Defer to Milestone 5.
- Should dark mode be supported via Tailwind's `dark:` modifier? Defer; brand palette is light-first.
