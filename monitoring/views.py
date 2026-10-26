from rest_framework.response import Response
from rest_framework.views import APIView
from django.db import connection

from accounts.permissions import IsApprover
from common.views import SqlListView


class AdminSqlView(SqlListView):
    permission_classes = [IsApprover]          # council sees every dashboard, same as admin


class Alerts(SqlListView):
    sql = "SELECT * FROM v_open_alerts"
    permission_classes = [IsApprover]


class Activity(AdminSqlView):
    sql = "SELECT * FROM v_recent_activity"


class FillRate(AdminSqlView):
    sql = "SELECT * FROM v_event_fill_rate"


class Trend(AdminSqlView):
    sql = "SELECT * FROM v_registration_trend"


class Health(AdminSqlView):
    sql = "SELECT * FROM v_db_health"


class Finance(AdminSqlView):
    sql = "SELECT * FROM event_finance"


class Stats(AdminSqlView):
    sql = "SELECT * FROM v_daily_stats_recent"


class ResolveAlert(APIView):
    permission_classes = [IsApprover]

    def post(self, request, alert_id):
        # The ONLY write the app makes to the monitoring tables.
        with connection.cursor() as cur:
            cur.execute("CALL sp_resolve_alert(%s)", [alert_id])
        return Response({"alert_id": alert_id, "resolved": True})
