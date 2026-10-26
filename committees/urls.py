from django.urls import path

from . import views

urlpatterns = [
    path("committees", views.CommitteeList.as_view()),
    path("committees/<int:committee_id>", views.CommitteeDetail.as_view()),
    path("committees/<int:committee_id>/members", views.CommitteeMemberAdd.as_view()),
]
