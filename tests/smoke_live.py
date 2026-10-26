"""
Live smoke test against a real, freshly seeded spit_events database (NOT a unit test suite yet).
    python tests/smoke_live.py
Creates throwaway accounts, then walks the main flows and prints PASS/FAIL per check.
"""
import os, sys, datetime
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django; django.setup()
from django.conf import settings
from django.db import connection, transaction
from django.test.utils import setup_test_environment; setup_test_environment()  # allows the 'testserver' host
from rest_framework.test import APIClient
from accounts.models import AppUser
from directory.models import Person
from events.models import Event

PW = "password123"
HALL = "Smoke Hall " + datetime.datetime.now().strftime("%H%M%S")
ROOT = settings.ROOT_ADMIN_EMAIL
D = "@" + settings.ALLOWED_EMAIL_DOMAIN
# Leftovers from a previous run (permanent rows are trigger-protected, so clear the flag in raw SQL first).
with connection.cursor() as cur:
    cur.execute("DROP TRIGGER IF EXISTS trg_app_user_permanent_delete")
    cur.execute("DROP TRIGGER IF EXISTS trg_app_user_permanent_update")
import importlib; m2 = importlib.import_module("accounts.migrations.0002_roles_committee_permanent")
AppUser.objects.all().delete()
Person.objects.filter(email__in=["smoke.new" + D, "ecell" + D]).delete()   # root's person row is seed data
with connection.cursor() as cur:
    for sql in m2.PERMANENT_ADMIN_TRIGGERS: cur.execute(sql)

def mk(pid, role="student", committee=None):
    return AppUser.objects.create_user(person=Person.objects.get(pk=pid), password=PW, role=role, committee_id=committee)

def login(email, pw=PW):
    c = APIClient()
    r = c.post("/api/auth/login", {"email": email, "password": pw}, format="json")
    assert r.status_code == 200, (email, r.content)
    c.credentials(HTTP_AUTHORIZATION="Token " + r.json()["token"]); return c
def client(pid): return login(Person.objects.get(pk=pid).email)

ok = bad = 0
def check(name, cond, extra=""):
    global ok, bad
    cond = bool(cond); ok += cond; bad += (not cond)
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else f"   -> {extra}"))

from django.core.management import call_command
call_command("create_app_user", email=ROOT, name="Anshul Pawar", password=PW, stdout=open(os.devnull, "w"))
root_u = AppUser.objects.get(person__email=ROOT)
check("root admin created permanent", root_u.role == "admin" and root_u.is_permanent)
check("root uses the seeded person row", root_u.person_id == 1 and root_u.person.name == "Anshul Pawar")
with connection.cursor() as cur:
    cur.execute("SELECT COUNT(*) FROM information_schema.TABLES WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'faculty'")
    no_table = cur.fetchone()[0] == 0
    cur.execute("SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = DATABASE() "
                "AND COLUMN_NAME IN ('faculty_id', 'hod_id')")
    no_cols = cur.fetchone()[0] == 0
check("faculty table and faculty columns are gone", no_table and no_cols)
check("seeded approvals belong to the root admin", set(Event.objects.filter(approval_status="Approved").values_list("approved_by_id", flat=True)) == {1})
mk(12, "admin"); mk(11, "council"); mk(5); mk(9); mk(19); mk(13); mk(6); mk(10)
root, adm, c11 = login(ROOT), client(12), client(11)
anon = APIClient()

# --- auth: domain, signup ---
r = anon.post("/api/auth/login", {"email": "x" + D, "password": "nope"}, format="json")
check("login wrong creds -> 401", r.status_code == 401)
r = anon.post("/api/auth/login", {"email": "someone@gmail.com", "password": PW}, format="json")
check("login non-spit domain -> 400", r.status_code == 400, r.content)
r = anon.post("/api/auth/signup", {"email": "x@gmail.com", "password": PW}, format="json")
check("signup non-spit domain -> 400", r.status_code == 400, r.content)
r = anon.post("/api/auth/signup", {"email": "Smoke.New" + D, "password": PW}, format="json")
check("signup -> 201 as student", r.status_code == 201 and r.json()["user"]["role"] == "student", r.content)
r = anon.post("/api/auth/signup", {"email": "smoke.new" + D, "password": PW}, format="json")
check("signup same email twice -> 400", r.status_code == 400, r.content)
r = anon.post("/api/auth/signup", {"email": ROOT, "password": PW}, format="json")
check("signup with root email -> 400", r.status_code == 400, r.content)
r = anon.post("/api/auth/signup", {"email": Person.objects.get(pk=21).email, "password": PW}, format="json")
check("directory person signs up, keeps their name", r.status_code == 201 and r.json()["user"]["name"] == Person.objects.get(pk=21).name, r.content)
r = anon.post("/api/auth/signup", {"email": "ecell" + D, "password": PW, "role": "admin"}, format="json")
ecell_id = r.json()["user"]["id"]
check("signup ignores a requested role", r.json()["user"]["role"] == "student", r.content)
check("no faculty role left", not AppUser.objects.filter(role="faculty").exists())

# --- public reads ---
check("public events list", anon.get("/api/events").status_code == 200 and len(anon.get("/api/events").json()) > 0)
check("pending event hidden from anon", anon.get("/api/events/5").status_code == 404)
check("committees list", anon.get("/api/committees").status_code == 200)
check("committee detail", anon.get("/api/committees/1").json().get("member_list"))
check("committee list has coordinator columns", "coordinator_name" in anon.get("/api/committees").json()[0])
check("lookups", all(anon.get(f"/api/{x}").status_code == 200 for x in ("categories", "venues")))

# --- account management ---
uid = lambda pid: AppUser.objects.get(person_id=pid).id
s9 = client(9)
r = s9.get("/api/admin/users"); check("student can't list accounts (403)", r.status_code == 403)
r = c11.get("/api/admin/users"); check("council lists accounts", r.status_code == 200 and len(r.json()) >= 9)
r = c11.patch(f"/api/admin/users/{uid(13)}", {"role": "council"}, format="json"); check("council promotes student -> council", r.status_code == 200 and r.json()["role"] == "council", r.content)
r = c11.patch(f"/api/admin/users/{uid(13)}", {"role": "admin"}, format="json"); check("council can't make admin (403)", r.status_code == 403, r.content)
r = c11.patch(f"/api/admin/users/{uid(12)}", {"role": "student"}, format="json"); check("council can't demote an admin (403)", r.status_code == 403, r.content)
r = c11.patch(f"/api/admin/users/{root_u.id}", {"is_active": False}, format="json"); check("council can't touch root (403)", r.status_code == 403, r.content)
r = c11.patch(f"/api/admin/users/{ecell_id}", {"role": "committee"}, format="json"); check("committee role needs a committee (400)", r.status_code == 400, r.content)
r = c11.patch(f"/api/admin/users/{ecell_id}", {"role": "committee", "committee": 1}, format="json"); check("council makes E-Cell committee account", r.status_code == 200 and r.json()["committee_name"] == "E-Cell", r.content)
r = adm.patch(f"/api/admin/users/{uid(13)}", {"role": "admin"}, format="json"); check("admin makes admin", r.status_code == 200, r.content)
r = adm.patch(f"/api/admin/users/{uid(13)}", {"is_permanent": True}, format="json"); check("non-root admin can't grant permanent (403)", r.status_code == 403, r.content)
r = root.patch(f"/api/admin/users/{uid(13)}", {"is_permanent": True}, format="json"); check("root grants permanent admin", r.status_code == 200 and r.json()["is_permanent"], r.content)
for who, c in (("admin", adm), ("root", root)):
    r = c.patch(f"/api/admin/users/{uid(13)}", {"role": "student"}, format="json"); check(f"{who} can't demote a permanent admin (403)", r.status_code == 403, r.content)
r = root.patch(f"/api/admin/users/{root_u.id}", {"role": "council"}, format="json"); check("root can't demote itself (403)", r.status_code == 403, r.content)
r = adm.patch(f"/api/admin/users/{root_u.id}", {"is_active": False}, format="json"); check("admin can't deactivate root (403)", r.status_code == 403, r.content)
def db_blocked(sql):
    try:
        with transaction.atomic(), connection.cursor() as cur: cur.execute(sql, [root_u.id])
        return False
    except Exception as e: return "permanent admin" in str(e)
check("DB trigger blocks raw demote of root", db_blocked("UPDATE app_user SET role='student' WHERE id=%s"))
check("DB trigger blocks raw delete of root", db_blocked("DELETE FROM app_user WHERE id=%s"))
r = adm.patch(f"/api/admin/users/{uid(10)}", {"role": "council"}, format="json"); r2 = adm.patch(f"/api/admin/users/{uid(10)}", {"role": "student"}, format="json")
check("admin promotes and demotes council", r.status_code == 200 and r2.status_code == 200, (r.content, r2.content))

# --- committees: council / admin manage, committee account edits its own coordinator only ---
CLUB = "Smoke Club " + HALL[-6:]
r = s9.post("/api/committees", {"name": CLUB, "email": "club" + HALL[-6:] + D}, format="json"); check("student can't add committee (403)", r.status_code == 403)
r = c11.post("/api/committees", {"name": CLUB, "email": "club" + HALL[-6:] + D, "founded_year": 2026,
                                 "coordinator_name": "Prof. X", "coordinator_email": "x" + D}, format="json")
check("council adds committee", r.status_code == 201 and r.json()["coordinator_name"] == "Prof. X", r.content)
club = r.json()["committee_id"]
r = adm.patch(f"/api/committees/{club}", {"coordinator_name": "Prof. Y"}, format="json"); check("admin edits committee", r.status_code == 200 and r.json()["coordinator_name"] == "Prof. Y", r.content)
c11.patch(f"/api/admin/users/{uid(21)}", {"role": "committee", "committee": club}, format="json")
r = c11.delete(f"/api/committees/{club}"); check("can't delete committee with a linked account (409)", r.status_code == 409 and "login account" in r.content.decode(), r.content)
c11.patch(f"/api/admin/users/{uid(21)}", {"role": "student"}, format="json")
r = c11.delete(f"/api/committees/{club}"); check("council deletes empty committee", r.status_code == 204, r.content)
r = c11.delete("/api/committees/1"); check("can't delete committee with events (409)", r.status_code == 409 and "has events" in r.content.decode(), r.content)

# --- events: only committee accounts post ---
d = datetime.date.today()
body = {"title": "Smoke Hack", "cat_id": 1, "fee": "100", "max_seats": 30,
        "reg_deadline": str(d + datetime.timedelta(days=5)),
        "sessions": [{"title": "Round 1", "session_date": str(d + datetime.timedelta(days=9)), "start_time": "10:00", "end_time": "12:00"}]}
ecell, s5 = login("ecell" + D), client(5)
check("committee account /me has its committee", ecell.get("/api/auth/me").json()["committees"][0]["committee_id"] == 1)
r = ecell.patch("/api/committees/1", {"coordinator_name": "Dr. Coordinator", "coordinator_email": "coord" + D}, format="json")
check("committee edits own coordinator", r.status_code == 200 and r.json()["coordinator_email"] == "coord" + D, r.content)
r = ecell.patch("/api/committees/1", {"name": "Renamed"}, format="json"); check("committee can't rename itself (403)", r.status_code == 403, r.content)
r = ecell.patch("/api/committees/2", {"coordinator_name": "Hijack"}, format="json"); check("committee can't edit another committee (403)", r.status_code == 403, r.content)
r = s5.patch("/api/committees/1", {"coordinator_name": "x"}, format="json"); check("student can't edit committee (403)", r.status_code == 403, r.content)
r = s5.post("/api/events", body, format="json"); check("student (even E-Cell president) can't post event (403)", r.status_code == 403, r.content)
r = c11.post("/api/events", body, format="json"); check("council can't post event (403)", r.status_code == 403, r.content)
r = ecell.post("/api/events", dict(body, committee_id=3), format="json"); check("committee posts event -> Pending", r.status_code == 201, r.content)
eid = r.json()["event_id"]
check("event is for the account's own committee", Event.objects.get(pk=eid).committee_id == 1)
r = ecell.patch(f"/api/admin/users/{uid(9)}", {"role": "committee", "committee": 1}, format="json"); check("committee can't grant access (403)", r.status_code == 403)
bad_body = dict(body, sessions=[dict(body["sessions"][0], session_date=str(d + datetime.timedelta(days=1)))])
r = ecell.post("/api/events", bad_body, format="json"); check("session before deadline -> 422 (trigger)", r.status_code == 422 and "before the registration deadline" in r.content.decode(), r.content)
check("new event not in public list", all(e["event_id"] != eid for e in anon.get("/api/events").json()))
check("committee sees own pending event", ecell.get(f"/api/events/{eid}").status_code == 200)
check("committee 'my events' lists it", any(e["event_id"] == eid for e in ecell.get("/api/me/events").json()))
r = s9.post(f"/api/events/{eid}/register"); check("register pending event -> 409", r.status_code == 409 and "not approved" in r.content.decode(), r.content)
r = s5.post(f"/api/events/{eid}/approve", {}, format="json"); check("student can't approve (403)", r.status_code == 403)
r = ecell.post(f"/api/events/{eid}/approve", {}, format="json"); check("committee can't approve (403)", r.status_code == 403)
check("council sees pending list", len(c11.get("/api/approvals/pending").json()["events"]) >= 2)
AppUser.objects.filter(person_id=5).update(role="council")
r = client(5).post(f"/api/events/{eid}/approve", {}, format="json"); check("council on the committee's roster can't approve it (403)", r.status_code == 403, r.content)
AppUser.objects.filter(person_id=5).update(role="student")
r = c11.post(f"/api/events/{eid}/approve", {"remarks": "ok"}, format="json"); check("COUNCIL approves event", r.status_code == 200, r.content)
check("approved_by = council person (11)", Event.objects.get(pk=eid).approved_by_id == 11)
r = adm.post(f"/api/events/{eid}/approve", {}, format="json"); check("re-deciding -> 409", r.status_code == 409, r.content)
r = c11.post("/api/events/5/reject", {"remarks": "no budget"}, format="json"); check("council rejects other event", r.status_code == 200, r.content)

# --- registration ---
r = s9.post(f"/api/events/{eid}/register"); check("student registers (201)", r.status_code == 201, r.content)
r = s9.post(f"/api/events/{eid}/register"); check("register twice -> 409", r.status_code == 409, r.content)
r = s9.get("/api/me/registrations"); check("my registrations lists it", any(x["event"] == "Smoke Hack" for x in r.json()), r.content)
r = s9.delete(f"/api/events/{eid}/register"); check("cancel registration", r.status_code == 200, r.content)
new = login("smoke.new" + D)
check("new signup has no tickets yet", new.get("/api/me/registrations").json() == [])
r = new.post(f"/api/events/{eid}/register"); check("new signup registers (student row made on the fly)", r.status_code == 201, r.content)
r = s9.post("/api/events/8/register"); check("deadline passed -> 409", r.status_code == 409 and "deadline" in r.content.decode(), r.content)
r = ecell.post(f"/api/events/{eid}/register"); check("committee account can't register (403)", r.status_code == 403)
r = adm.post(f"/api/events/{eid}/register"); check("admin can't register (403)", r.status_code == 403)
r = anon.post(f"/api/events/{eid}/register"); check("register needs login", r.status_code == 401)

# --- venues: manage ---
r = s9.post("/api/venues", {"venue_name": HALL, "capacity": 100}, format="json"); check("student can't add venue (403)", r.status_code == 403)
r = ecell.post("/api/venues", {"venue_name": HALL, "capacity": 100}, format="json"); check("committee can't add venue (403)", r.status_code == 403)
r = c11.post("/api/venues", {"venue_name": HALL, "capacity": 100, "location": "Ground floor"}, format="json")
check("council adds venue", r.status_code == 201 and r.json()["status"] == "Active", r.content)
vid = r.json()["venue_id"]
check("new venue in public list", any(v["venue_id"] == vid for v in anon.get("/api/venues").json()))
r = adm.patch(f"/api/venues/{vid}", {"capacity": 120}, format="json"); check("admin edits venue", r.status_code == 200 and r.json()["capacity"] == 120, r.content)

# --- venues: bookings, suspend -> flag -> keep / cancel ---
r = s9.post(f"/api/events/{eid}/sessions/1/bookings", {"venue_id": vid}, format="json"); check("student can't book (403)", r.status_code == 403)
r = ecell.post(f"/api/events/{eid}/sessions/1/bookings", {"venue_id": vid}, format="json"); check("committee requests venue", r.status_code == 201, r.content)
r = ecell.post(f"/api/events/{eid}/sessions/1/bookings", {"venue_id": 99}, format="json"); check("bad venue id -> 422", r.status_code == 422, r.content)
r = ecell.post(f"/api/events/{eid}/sessions/1/bookings", {"venue_id": 2}, format="json"); check("committee requests 2nd venue (Room 103)", r.status_code == 201, r.content)
r = c11.post(f"/api/events/{eid}/sessions/1/bookings/{vid}/approve"); check("council approves booking", r.status_code == 200, r.content)
r = anon.get(f"/api/venues/{vid}/availability?date={d + datetime.timedelta(days=9)}"); check("availability shows booking", len(r.json()["bookings"]) >= 1, r.content)

r = c11.patch(f"/api/venues/{vid}", {"status": "Suspended"}, format="json"); check("council suspends venue", r.status_code == 200 and r.json()["flagged"] == 1, r.content)
check("suspended venue hidden from public list", all(v["venue_id"] != vid for v in anon.get("/api/venues").json()))
check("council sees it with ?all=1", any(v["venue_id"] == vid and v["status"] == "Suspended" for v in c11.get("/api/venues?all=1").json()))
fl = c11.get("/api/approvals/pending").json()["flagged_bookings"]
check("flagged booking listed for council", any(f["venue_id"] == vid and f["event_id"] == eid for f in fl), fl)
check("alert raised for suspended venue", any(a["alert_type"] == "VENUE_UNAVAILABLE" for a in adm.get("/api/admin/alerts").json()))
r = ecell.post(f"/api/events/{eid}/sessions/1/bookings", {"venue_id": vid}, format="json")
check("new request on suspended venue blocked", r.status_code in (409,) , r.content)
r = s9.post(f"/api/events/{eid}/sessions/1/bookings/{vid}/keep"); check("student can't decide flag (403)", r.status_code == 403)
r = c11.post(f"/api/events/{eid}/sessions/1/bookings/{vid}/keep"); check("council KEEPS flagged booking", r.status_code == 200, r.content)
check("kept booking still Approved, unflagged", not c11.get("/api/approvals/pending").json()["flagged_bookings"])

r = c11.patch(f"/api/venues/{vid}", {"status": "Active"}, format="json"); check("council reactivates venue", r.status_code == 200 and r.json()["status"] == "Active")
r = c11.delete("/api/venues/2"); check("council removes Room 103 (soft)", r.status_code == 200 and r.json()["status"] == "Removed", r.content)
r = c11.post(f"/api/events/{eid}/sessions/1/bookings/2/approve"); check("can't approve booking at removed venue (409)", r.status_code == 409, r.content)
r = c11.post(f"/api/events/{eid}/sessions/1/bookings/2/cancel"); check("council CANCELS flagged booking", r.status_code == 200, r.content)
r = anon.get(f"/api/events/{eid}")
st = {s["venue_id"]: s["booking_status"] for s in r.json()["sessions"]}
check("cancelled booking is Rejected, kept one Approved", st.get(2) == "Rejected" and st.get(vid) == "Approved", st)
c11.patch("/api/venues/2", {"status": "Active"}, format="json")

# --- dashboards: council sees everything admin sees ---
for p in ("alerts", "activity", "fill-rate", "trend", "health", "finance", "stats"):
    check(f"council + admin see admin/{p}", c11.get(f"/api/admin/{p}").status_code == 200 and adm.get(f"/api/admin/{p}").status_code == 200)
check("student blocked from dashboards (403)", s9.get("/api/admin/finance").status_code == 403)
check("committee blocked from dashboards (403)", ecell.get("/api/admin/finance").status_code == 403)
a = adm.get("/api/admin/activity").json()
check("activity JSON parsed (dict not str)", (not a) or isinstance(a[0].get("new_data"), (dict, type(None))), a[:1])
al = c11.get("/api/admin/alerts").json()
if al:
    check("council resolves alert", c11.post(f"/api/admin/alerts/{al[0]['alert_id']}/resolve").status_code == 200)

# --- deactivation ---
r = c11.patch(f"/api/admin/users/{uid(6)}", {"is_active": False}, format="json")
r2 = APIClient().post("/api/auth/login", {"email": Person.objects.get(pk=6).email, "password": PW}, format="json")
check("deactivated account can't log in", r.status_code == 200 and r2.status_code == 401, (r.content, r2.content))

print(f"\n{ok} passed, {bad} failed")
sys.exit(1 if bad else 0)
