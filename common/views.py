from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .db import fetch_all


class SqlListView(APIView):
    """Read-only endpoint that returns every row of a fixed SQL query. Subclass and set `sql`."""
    sql = ""
    permission_classes = [AllowAny]

    def get(self, request):
        return Response(fetch_all(self.sql))
