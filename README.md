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

#or
mysql -u root -p
source sql/01_schema.sql
source sql/02_sample_data.sql 

# 2. Django's own tables + app_user (login accounts, permanent-admin trigger)
python manage.py migrate

# 3. The root admin (permanent; creates the person row if needed)
python manage.py create_app_user --email anshul.pawar25@spit.ac.in

python manage.py runserver
```

## UI

`python manage.py runserver`, then open http://127.0.0.1:8000/ . 

| Page | For |
|---|---|
| `index.html`, `event.html` | everyone: browse, event detail, register / cancel (students) |
| `my.html` | student tickets |
| `login.html` | log in, or sign up (`#signup`) with an @spit.ac.in email |
| `committee.html` | committee accounts: my events, new event, request venue |
| `approvals.html` | council / admin: approve / reject events and venue bookings, keep / cancel flagged bookings |
| `admin.html` | council / admin dashboard: stats, alerts, activity log, accounts, venues |


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
The hook is `registrations/payments.py`; will swap `PAYMENT_GATEWAY` in settings  when real one will exist

## Try it

```bash
python tests/smoke_live.py    # walks the main flows against a freshly seeded DB (113 checks)
```

## Layout

```
config/         settings, root urls
sql/            01_schema (final schema), 02_sample_data, 90_trigger_tests
common/         DB helpers, trigger-error -> HTTP mapping, exception handler
accounts/       app_user (the only Django-managed table of ours), login, permissions, admin user mgmt
directory/      person / student / lookups (unmanaged models)
committees/  events/  venues/  registrations/  monitoring/
```
