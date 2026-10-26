from django.urls import path

from common.views import SqlListView

from . import mine, views


class Categories(SqlListView):
    sql = "SELECT cat_id, cat_name FROM category ORDER BY cat_name"


urlpatterns = [
    path("me/events", mine.MyCommitteeEvents.as_view()),
    path("events", views.EventListCreate.as_view()),
    path("events/<int:event_id>", views.EventDetail.as_view()),
    path("events/<int:event_id>/approve", views.EventDecision.as_view(decision="Approved")),
    path("events/<int:event_id>/reject", views.EventDecision.as_view(decision="Rejected")),
    path("approvals/pending", views.PendingApprovals.as_view()),
    path("categories", Categories.as_view()),
]
