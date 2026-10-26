# SPIT Event Management (Django + MySQL)

JSON API over the `spit_events` MySQL database, plus a plain HTML/CSS/JS front end (Bauhaus style) in `web/`.
Business rules live in MySQL triggers. Django only translates their errors into clean HTTP responses.

## Setup

```bash
python -m venv venv && source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env    # then export those vars, or set them in your shell

# 1. Build the database (use the mysql CLI: the file has DELIMITER blocks)
mysql -u root -p < sql/01_schema.sql
mysql -u root -p < sql/02_sample_data.sql        # optional demo data

# 2. Django's own tables + app_user (login accounts, permanent-admin trigger)
python manage.py migrate

# 3. The root admin (permanent; creates the person row if needed)
python manage.py create_app_user --email anshul.pawar25@spit.ac.in

python manage.py runserver
```

Order matters: SQL first, then `migrate` (app_user has a foreign key to `person`).

### Upgrading a database built from the old schema (with faculty)

Don't rebuild; run the upgrade patches in this order (each one says what it changes):

```bash
mysql -u root -p < sql/upgrade/10_approver_patch.sql      # skip if you already ran it
mysql -u root -p < sql/upgrade/20_roles_venues_patch.sql
python manage.py migrate
python manage.py create_app_user --email anshul.pawar25@spit.ac.in --name "Anshul Pawar"
mysql -u root -p < sql/upgrade/30_drop_faculty_patch.sql  # needs the root admin: faculty approvals move to him
```

The result is structurally identical to a fresh `01_schema.sql` build.

### Cleaning up an existing database (v3 to v4)

v4 removes what nothing used (see `sql/upgrade/40_cleanup_patch.sql` for the full list), closes a hole where a
venue could be approved for an unapproved event, and makes the "waiting for approval" alerts close themselves.
Your data and login accounts stay. One command:

```bash
mysql -u root -p < sql/upgrade/40_cleanup_patch.sql
```

It deletes `student.year / division / dob / dept_id` and `person.street / city_id` with their data, since the app never filled them.
Checked on a v3 database: same row counts afterwards, and the structure matches a fresh v4 build (same 31 triggers, tables and views).

## UI

`python manage.py runserver`, then open http://127.0.0.1:8000/ . Django serves `web/` itself (same origin as `/api`, no CORS, no build step).

| Page | For |
|---|---|
| `index.html`, `event.html` | everyone: browse, event detail, register / cancel (students) |
| `my.html` | student tickets |
| `login.html` | log in, or sign up (`#signup`) with an @spit.ac.in email |
| `committee.html` | committee accounts: my events, new event, request venue |
| `approvals.html` | council / admin: approve / reject events and venue bookings, keep / cancel flagged bookings |
| `admin.html` | council / admin dashboard: stats, alerts, activity log, accounts, venues |

Added for the UI (additive): `GET /api/me/events` (events.mine), `GET /api/me/registrations/full` (registrations.mine), `WEB_DIR` in settings and the static route in `config/urls.py`.

## Who can do what

Four roles, one per account (`app_user.role`):

| Role | Can |
|---|---|
| anyone | browse approved events, committees, active venues |
| **student** | register / cancel, see own registrations. Every new account starts here |
| **committee** | a committee's own account (e.g. `ecell@spit.ac.in`, linked via `app_user.committee_id`): post events and request venues for that committee only. Can't grant access to anyone |
| **council** | approve / reject events and bookings; add, suspend, remove venues; see every dashboard (finance, activity, alerts); change accounts up to council level. Can also register (council members are students) |
| **admin** | everything council can + make admins |

- **Login / signup**: only `@spit.ac.in` emails. Signup asks for email + password only; the student row
  (roll no = part before the @) is created on the first registration.
- **Permanent admins**: can't be demoted, deactivated or deleted by anyone, including themselves. Enforced
  in the app and by triggers on `app_user` (`trg_app_user_permanent_*`). Only the root admin
  (`ROOT_ADMIN_EMAIL`, default `anshul.pawar25@spit.ac.in`) can make another admin permanent. The root
  email can't be taken through signup; create it with `create_app_user`.
- **Self-approval**: a council member on a committee's roster (`committee_member`) can't decide that committee's
  events or bookings. The roster itself grants no rights.
- **Venues**: `venue.status` is Active / Suspended / Removed (removed = soft delete, history stays). Only active
  venues can be requested or approved (triggers). Suspending or removing a venue flags its upcoming bookings
  (`venue_booking.flagged`, trigger `trg_venue_status_flag`) and raises an alert; the council keeps or cancels
  each one. Reactivating clears the flags.
- **Faculty**: gone completely: no faculty table, role, people or `department.hod_id`. A committee's coordinator
  is plain contact details on the committee row (`coordinator_name`, `coordinator_email`, both optional).
- **Committees**: council / admin add, edit and delete them (delete only while a committee has no events and no
  linked login). A committee's own account can edit only its coordinator details.

## Auth

`POST /api/auth/login {email, password}` returns a token. Send `Authorization: Token <token>`.

## Payment

No gateway. Registering just records the registration (`amount_paid` stays 0).
The hook is `registrations/payments.py`; swap `PAYMENT_GATEWAY` in settings when a real one exists.

## Try it

```bash
python tests/smoke_live.py    # walks the main flows against a freshly seeded DB (113 checks)
```

## Layout

```
config/         settings, root urls
sql/            01_schema (final schema), 02_sample_data, 90_trigger_tests
sql/upgrade/    10, 20, 30, 40 patches: only for a database built from an older schema
common/         DB helpers, trigger-error -> HTTP mapping, exception handler
accounts/       app_user (the only Django-managed table of ours), login, permissions, admin user mgmt
directory/      person / student / lookups (unmanaged models)
committees/  events/  venues/  registrations/  monitoring/
```

## Not built yet
- editing a student's roll number after signup
- scheduled jobs (cron or MySQL event scheduler)
- real test suite (the smoke script is a stopgap; needs a runner that loads sql/ into the test DB)
