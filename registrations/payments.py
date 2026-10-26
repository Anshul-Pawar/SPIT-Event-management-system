"""
Payment hook. There is NO gateway yet: registering just records the registration.

When a real gateway exists:
  1. write a class with the same `charge` signature (redirect/confirm flow goes inside it),
  2. point settings.PAYMENT_GATEWAY at it.
The registration view doesn't change.

amount_paid stays 0 while nothing is actually collected, so event_finance doesn't report income that
never happened. (fee > 0 and amount_paid = 0 therefore means "registered, not paid".)
"""
from dataclasses import dataclass
from decimal import Decimal

from django.conf import settings
from django.utils.module_loading import import_string


@dataclass
class PaymentResult:
    amount_paid: Decimal
    reference: str | None = None   # gateway transaction id, once one exists


class RecordOnlyGateway:
    def charge(self, *, student_id: int, event_id: int, amount: Decimal) -> PaymentResult:
        # TODO(payments): create the gateway order here and return what was really paid.
        return PaymentResult(amount_paid=Decimal("0"))


def get_gateway():
    return import_string(settings.PAYMENT_GATEWAY)()
