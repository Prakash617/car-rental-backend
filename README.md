# Car Rental SaaS — Backend Service

The core multi-tenant backend API for the Car Rental SaaS platform, powered by Django 5, Django REST Framework, `django-tenants`, PostgreSQL schemas, Redis, and Celery.

---

## Architecture Highlights

- **Schema Multi-Tenancy**: Isolated PostgreSQL schema per tenant (`public` vs `tenant_<id>`).
- **Zero Cross-Tenant Contamination**: Server-side tenant resolution inferred strictly from the incoming `Host` header.
- **Defense-in-Depth Concurrency**: Dynamic availability calculation, pessimistic row locking (`select_for_update()`), and PostgreSQL `btree_gist` exclusion constraints.
- **Asynchronous Processing**: Background workers and Celery Beat periodic tasks running inside tenant schema contexts.
- **API Documentation**: Automated OpenAPI 3.0 generation via `drf-spectacular`.

---

## Directory Structure

```text
backend/
├── config/
│   ├── settings/
│   │   ├── base.py          # Shared settings across all environments
│   │   ├── development.py   # Development-specific overrides
│   │   ├── production.py    # Production security & cache settings
│   │   └── testing.py       # In-memory fast test configurations
│   ├── urls.py              # Root public & tenant routing
│   ├── asgi.py              # ASGI configuration
│   ├── wsgi.py              # WSGI entrypoint for Gunicorn
│   └── celery.py            # Celery worker and task queue setup
│
├── apps/
│   ├── platform/            # Public schema apps (Tenants, Domains, Plans, Themes)
│   └── tenant/              # Tenant schema apps (Vehicles, Bookings, Pricing, etc.)
│
├── common/                  # Shared exceptions, permissions, pagination, middleware
├── integrations/            # Payment gateways, email, storage, SMS
├── tests/                   # Isolation, concurrency, integration, and unit tests
├── pyproject.toml           # Dependency specifications managed via uv
└── Dockerfile               # Multi-stage container definition
```

---

## Local Development Setup

1. **Install dependencies with uv**:
   ```bash
   uv sync --all-extras
   ```

2. **Setup environment variables**:
   ```bash
   cp .env.example .env
   ```

3. **Run database migrations**:
   ```bash
   uv run python manage.py migrate_schemas
   ```

4. **Start development server**:
   ```bash
   uv run python manage.py runserver 0.0.0.0:8000
   ```

5. **Start Celery worker**:
   ```bash
   uv run celery -A config worker --loglevel=info
   ```

6. **Run tests**:
   ```bash
   uv run pytest
   ```
