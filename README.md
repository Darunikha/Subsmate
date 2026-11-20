# Subsmate – Subscription & Renewal Management Platform

Subsmate helps service businesses manage customer subscriptions, track renewal dates and payments, and avoid missed renewals.

**Stack:** React 18 + Recharts (Vite) · Flask 3 + Flask-SQLAlchemy · SQLite · Pytest · Docker Compose · GitHub Actions · Terraform · Ansible · Kubernetes · Prometheus + Grafana

---

## Quick start

### Option A: Docker Compose (recommended)

```bash
cp .env.example .env            # set SECRET_KEY
docker compose up --build
```

Open **http://localhost:8090**. The SQLite database lives in the `subsmate-data` volume, so data survives restarts.

To add monitoring, run `docker compose --profile monitoring up --build`. Prometheus is then at http://localhost:9090 and Grafana at http://localhost:3000 (`admin` / `admin`). Grafana loads the "Subsmate Overview" dashboard automatically.

### Option B: Run locally without Docker

```bash
# Backend: http://localhost:5000
cd backend
python -m venv .venv
.venv/Scripts/activate            # Windows  (macOS/Linux: source .venv/bin/activate)
pip install -r requirements-dev.txt
python run.py

# Frontend: http://localhost:5173, proxies /api to :5000
cd frontend
npm install
npm run dev
```

On first start, an empty database is filled with realistic demo data, dated relative to today. Set `SEED_DEMO_DATA=false` to start empty.

### Demo accounts

| Role | Email | Password |
|---|---|---|
| Administrator | admin@subsmate.io | Admin@123 |
| Staff | staff@subsmate.io | Staff@123 |
| Customer | priya.sharma@brightdental.com | Customer@123 |

The login page has one-click buttons that fill in each account.

---

## Features

| Module | What it does |
|---|---|
| **Dashboard** | Monthly revenue (vs. the same period last month), active subscriptions, upcoming renewals, customer count, 6-month revenue chart, status overview, upcoming renewals and recent activity. Customers see a personal version. All figures come from the database. |
| **Customers** | Register, edit, search (name, email or phone), set active/inactive, optional portal login, and full subscription and payment history. Customers that have history can't be deleted; they're deactivated instead. |
| **Subscriptions** | Create, edit, cancel and renew. Each subscription carries its own service name, billing cycle (monthly, quarterly or yearly) and amount. The expiry date is calculated from the billing cycle, and the status (Active, Expiring soon, Expired or Cancelled) is derived from dates. Can be filtered by status and searched. |
| **Renewals** | Overdue (red), expiring within 7 days (orange) and later in the window (green), with a selectable 7–90 day window (30 by default). One-click renew and full renewal history. |
| **Payments** | Record payments manually, mark them paid, update status (Paid, Pending or Failed), filter by status, overdue or date range, and see totals by status. |
| **Reports** | Revenue, active and expired counts, pending payments, service popularity, customer distribution and renewal trends, with a date-range filter and 7 CSV exports. |
| **Notifications** | In-app renewal reminders, expiry alerts and failed-payment alerts, created automatically with no duplicates. |
| **Settings** | Profile, password change, and (for admins) user and role management. |

### Role permissions

| Capability | Admin | Staff | Customer |
|---|:-:|:-:|:-:|
| Manage users | ✓ | | |
| Register and edit customers | ✓ | ✓ | |
| Delete customers | ✓ | | |
| Create, edit and cancel subscriptions | ✓ | ✓ | own only, read-only |
| Renew subscriptions | ✓ | ✓ | |
| Record and update payments | ✓ | ✓ | own history, read-only |
| Reports and CSV export | ✓ | | |

Staff is a single day-to-day operations role covering what the brief describes as Sales Executive and Billing Officer. To separate selling from payment handling again, split `ROLE_STAFF` in `backend/app/models.py` and adjust the `roles_required` decorators.

These permissions are enforced by the API, not only hidden in the UI. Customers can only ever query their own records.

### Business rules

1. **Expiry dates** are the start date plus 1, 3 or 12 calendar months, clamped to the last day of the month (Jan 31 + 1 month = Feb 28/29).
2. **Statuses** are derived and never go stale. Cancelled comes from the cancelled flag. Otherwise a subscription is Expired once its expiry date has passed, Expiring soon if it expires within 7 days (`EXPIRING_SOON_DAYS`), and Active otherwise.
3. **Upcoming renewals** cover live subscriptions expiring within 30 days (`RENEWAL_WINDOW_DAYS`). Overdue ones are listed separately.
4. **Renewing** extends from the current expiry date, so no paid time is lost. If the subscription has already expired, the new period starts today. Each renewal writes a `renewal_history` row and a new payment record (pending unless marked paid). Earlier payments and renewals are never changed or deleted.
5. **Revenue** counts only payments with status `paid`, dated by `paid_on`.
6. A subscription's payment status mirrors its most recent payment.
7. A customer can't hold two current subscriptions to the same service (names are compared ignoring case).

---

## Deploy to Render (one service)

The root `Dockerfile` builds the React app and serves it together with the API from a single process, so only one service is needed. There is no CORS or API-URL setup.

1. Push this repo to GitHub.
2. In Render choose **New + → Blueprint**, select the repo and click **Apply**. `render.yaml` creates the service and a random `SECRET_KEY`.
3. When the build finishes, open the `.onrender.com` address and sign in with a demo account.

You can try the same image locally with `docker build -t subsmate . && docker run -p 5000:5000 -e SECRET_KEY=change-me subsmate`, then open http://localhost:5000.

**Limits of the free setup:**
- The free tier's disk is wiped on every restart or redeploy, so data resets to the demo data. That is fine for a demo. For real data, add a persistent disk mounted at `/data` (paid plan) or move to PostgreSQL.
- The free service sleeps when idle, so the first request after a pause can take 30–60 seconds.
- Demo accounts are public. For real use, set `SEED_DEMO_DATA=false` and create real users in Settings.

## Project structure

```
backend/
  app/
    __init__.py        app factory, error handlers, health check
    config.py          env-driven configuration
    extensions.py      SQLAlchemy (+ SQLite foreign keys)
    models.py          Users, Customers, Subscriptions,
                       Payments, RenewalHistory, Notifications
    auth.py            signed bearer tokens, role decorators
    utils.py           validation, errors, pagination
    services/          dates, subscriptions, payments, notifications, analytics
    routes/            auth, users, customers, subscriptions,
                       payments, renewals, insights (dashboard/reports/search)
    metrics.py         Prometheus /metrics
    seed.py            demo data
  tests/               pytest suite (85 tests)
frontend/
  src/lib/             api client, auth context, hooks, formatters
  src/components/      layout, UI kit, forms, charts
  src/pages/           one file per screen
monitoring/            Prometheus config, alerts, Grafana provisioning and dashboard
k8s/                   Kubernetes manifests (app + monitoring)
terraform/             Docker-provider infrastructure definition
ansible/               server configuration and deployment playbook
.github/workflows/     CI: tests, build, Docker smoke test
```

## API overview

All endpoints are under `/api` and need `Authorization: Bearer <token>`, except `/auth/login` and `/health`.

| Endpoint | Methods |
|---|---|
| `/auth/login`, `/auth/me`, `/auth/change-password` | POST · GET/PUT · POST |
| `/users[/<id>]` | GET POST · PUT DELETE |
| `/customers[/<id>]` | GET POST · GET PUT DELETE |
| `/subscriptions[/<id>]` | GET POST · GET PUT |
| `/subscriptions/<id>/cancel`, `/subscriptions/<id>/renew` | POST |
| `/payments[/<id>]` | GET POST · GET PUT |
| `/renewals/upcoming?days=30`, `/renewals/history` | GET |
| `/dashboard`, `/search?q=`, `/notifications` | GET |
| `/reports/summary?from&to`, `/reports/export/<report>?from&to` | GET (CSV) |

The export reports are `revenue`, `payments`, `pending-payments`, `subscriptions`, `services`, `renewals` and `customers`.

Errors are returned as JSON (`{"error": "...", "errors": {"field": "..."}}`) with these status codes: 400 bad request, 401 unauthenticated, 403 forbidden, 404 not found, 409 conflict, 422 validation.

## Testing

```bash
cd backend && pytest -q
```

The suite covers authentication, password hashing, token invalidation, customer registration and CRUD, subscription creation, expiry calculation including month-end edge cases, status detection, renewals (including history preservation and billing-cycle changes), cancellation, payment recording and status updates, revenue calculations, role-based access control, customer data isolation, reports, CSV exports and metrics.

## DevOps

- **GitHub Actions** (`.github/workflows/ci.yml`): on every push it runs pytest, builds the frontend, builds both Docker images, and smoke-tests the composed stack through the nginx proxy.
- **Docker**: the backend runs on gunicorn as a non-root user with a health check. The frontend is a static build served by nginx, which proxies `/api` to the backend. The database volume is mounted at `/data`.
- **Terraform** (`terraform/`): defines the network, volume, images and containers with the `kreuzwerker/docker` provider. It runs against local Docker, or against a remote host via `docker_host = "ssh://..."`.
  ```bash
  cd terraform && cp terraform.tfvars.example terraform.tfvars
  terraform init && terraform apply
  ```
- **Ansible** (`ansible/`): installs Docker on an Ubuntu server, syncs the app, writes `.env` and starts Compose. Optionally it also starts the monitoring stack.
  ```bash
  ansible-playbook -i ansible/inventory.ini ansible/playbook.yml -e subsmate_secret_key=$(openssl rand -hex 32)
  ```
- **Kubernetes** (`k8s/`): namespace, ConfigMap, PVC, backend Deployment (one replica with Recreate strategy, because SQLite allows a single writer), frontend Deployment, Services, Ingress, and an optional Prometheus/Grafana deployment. Setup steps are at the top of `k8s/subsmate.yaml`.
- **Monitoring**: `/metrics` exports request counts and latency, plus business gauges: subscriptions by status, customers, pending payments and current-month revenue. Prometheus has alert rules for the backend being down, error rate and expired subscriptions.

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `SECRET_KEY` | dev value | Signs auth tokens. **Set this in production.** |
| `DATABASE_URL` | `sqlite:///backend/instance/subsmate.db` | SQLAlchemy database URL |
| `TOKEN_MAX_AGE` | `43200` | Session length in seconds |
| `EXPIRING_SOON_DAYS` | `7` | Expiring-soon threshold |
| `RENEWAL_WINDOW_DAYS` | `30` | Upcoming-renewals window |
| `SEED_DEMO_DATA` | `true` | Seed an empty database |
| `CORS_ORIGINS` | `*` | Allowed origins for `/api` |

## Notes and next steps

- SQLite suits a single instance. To scale out, point `DATABASE_URL` at PostgreSQL; the models are portable, but the report queries use SQLite's `strftime` and would need adjusting.
- The schema is created with `db.create_all()`. Add Flask-Migrate (Alembic) before evolving the schema in production.
- Payment gateways and email/SMS reminders are deliberately left out. Reminders appear in the app.
