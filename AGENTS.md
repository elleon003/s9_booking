# AGENTS.md

High-signal notes for OpenCode sessions working in this repo.

## Environment & invocation

- Python virtualenv lives at `.venv/`. Use `.venv/bin/python manage.py <cmd>` (or activate `.venv` first). The global interpreter does not have Django installed.
- Not a git repository. Do not run git commands or attempt commits/PRs.
- Django 6.0 project. Package: `config` (project), `theme` (Tailwind app). No local business apps exist yet.

## Settings

- Split settings: `config/settings/{base,dev,prod}.py`. `manage.py` hardcodes `DJANGO_SETTINGS_MODULE=config.settings.dev`, so dev runs need no env var. Prod requires `DJANGO_SETTINGS_MODULE=config.settings.prod` plus a full env set (see `prod.py`).
- Env loading via `environs`: `base.py` calls `env = Env(); env.read_env()`, which auto-discovers `.env` by recursing up from the CWD. A `.env` file at the project root is **required even in dev** — `base.py` reads `SECRET_KEY` with no default before `dev.py`'s default applies. A committed `.env.example` is provided; copy it to `.env` for local development:
  ```bash
  cp .env.example .env
  ```
  Then override `SECRET_KEY` and any other local values. Do not commit `.env`. Minimum dev `.env`:
  ```
  SECRET_KEY=django-insecure-...
  DEBUG=True
  ALLOWED_HOSTS=localhost,127.0.0.1,::1,s9booking.local,.s9booking.local
  BASE_HOST=s9booking.local
  DEFAULT_FROM_EMAIL=dev@s9booking.local
  ```
- If a session reports `EnvError: Environment variable "SECRET_KEY" not set`, create/repair `.env` (from `.env.example`) rather than editing settings.

## Verification commands

- `manage.py check` — primary sanity check. Expect one standing warning: `staticfiles.W004` (top-level `static/` dir in `STATICFILES_DIRS` does not exist). This is harmless and expected; do not "fix" it by removing the setting.
- `manage.py migrate` — SQLite (`db.sqlite3` at repo root) in dev. Migrations are already applied.
- There is **no test suite, no linter, and no typechecker configured**. Do not claim to run tests/lint/typecheck. No `pyproject.toml`, no `pytest.ini`, no ruff/mypy config. `requirements-dev.txt` only adds `django-browser-reload`, `honcho`, `pip-review` (no Procfile exists yet).

## Unfold admin

- `unfold` + contrib (`filters`, `forms`, `inlines`) must stay **before** `django.contrib.admin` in `INSTALLED_APPS` (`base.py`). Unfold will not render if ordered after.
- `UNFOLD` settings dict lives in `base.py`. `STYLES` references the compiled Tailwind output at `static('css/dist/styles.css')` (served from `theme/static/`).
- When changing Unfold config, verify rendering with the test client against `/admin/login/` (host must be in `ALLOWED_HOSTS`, e.g. `HTTP_HOST='127.0.0.1'`).

## Tailwind (django-tailwind v4)

- `TAILWIND_APP_NAME = 'theme'`. The `theme/` app uses **Tailwind v4** (`@tailwindcss/postcss`, `@import 'tailwindcss';` in `theme/static_src/src/styles.css`). There is **no `tailwind.config.js`** — v4 config lives in CSS; do not create one expecting v3 semantics.
- Node.js + npm required. Build commands:
  - `manage.py tailwind install` — `npm install` + production build into `theme/static/css/dist/styles.css`.
  - `manage.py tailwind start` — watch mode for dev. Run in a separate terminal.
  - `manage.py tailwind build` — one-off production build.
- After editing `UNFOLD['STYLES']` or the Tailwind source, rebuild CSS or the admin won't reflect changes.

## Dev server gotcha

- `dev.py` adds `django_browser_reload` to `INSTALLED_APPS` and `config/urls.py` mounts it under `__reload__/` when `DEBUG`, but `INTERNAL_IPS` is **never set in dev** (only `prod.py` sets it). Browser reload will not actually trigger until you add `INTERNAL_IPS = ['127.0.0.1']` to `dev.py` or your `.env`.

## Docs

- `docs/sage-nine-creative-brand-guidelines.md` — brand/voice reference for the "Sage Nine Creative" product (this is their booking app). Consult for naming, tone, and branding decisions.