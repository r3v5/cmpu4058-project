from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

from ai_datacenters.forms import LoginForm

urlpatterns = [
    path("admin/", admin.site.urls),
    # Before the auth URLs, so this login view (custom form, redirect for
    # users who are already logged in) wins over the default one.
    path(
        "accounts/login/",
        auth_views.LoginView.as_view(authentication_form=LoginForm, redirect_authenticated_user=True),
        name="login",
    ),
    path("accounts/", include("django.contrib.auth.urls")),
    path("", include("ai_datacenters.urls")),
]
