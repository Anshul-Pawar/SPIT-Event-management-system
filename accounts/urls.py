from django.urls import path

from . import views

urlpatterns = [
    path("auth/login", views.LoginView.as_view()),
    path("auth/signup", views.SignupView.as_view()),
    path("auth/logout", views.LogoutView.as_view()),
    path("auth/me", views.MeView.as_view()),
    path("admin/users", views.UserList.as_view()),
    path("admin/users/<int:pk>", views.UserDetail.as_view()),
]
