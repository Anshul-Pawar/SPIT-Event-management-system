import logging

from django.db import DatabaseError
from rest_framework.response import Response
from rest_framework.views import exception_handler

from .errors import map_db_error

log = logging.getLogger("spit")


def api_exception_handler(exc, context):
    """Standard DRF handling, plus: DB/trigger errors become clean JSON, never raw SQL."""
    response = exception_handler(exc, context)
    if response is not None:
        return response

    if isinstance(exc, DatabaseError):
        mapped = map_db_error(exc)
        if mapped:
            status, message = mapped
            return Response({"error": message}, status=status)
        log.exception("Unmapped database error")
        return Response({"error": "Something went wrong on our side"}, status=500)

    return None  # let Django produce its normal 500
