from django.urls import path

from .views import SecureLoginView, signup

urlpatterns = [
    path("signup/", signup, name="signup"),
    # overrides django.contrib.auth's login (included after this app in config/urls.py)
    path("login/", SecureLoginView.as_view(), name="login"),
]
