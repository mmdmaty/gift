import math

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.views import LoginView
from django.shortcuts import redirect, render

from .forms import SignUpForm
from .models import SiteSettings
from .security import (
    clear_failures,
    failure_count,
    get_client_ip,
    lockout_remaining_seconds,
    register_failure,
)


class SecureLoginView(LoginView):
    redirect_authenticated_user = True

    def post(self, request, *args, **kwargs):
        if lockout_remaining_seconds(get_client_ip(request)):
            # banned IPs don't even get their credentials checked
            context = self.get_context_data(form=self.get_form_class()(request))
            return self.render_to_response(context, status=429)
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        clear_failures(get_client_ip(self.request))
        return super().form_valid(form)

    def form_invalid(self, form):
        ip = get_client_ip(self.request)
        register_failure(ip)
        response = super().form_invalid(form)
        if lockout_remaining_seconds(ip):
            response.status_code = 429
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        ip = get_client_ip(self.request)
        remaining = lockout_remaining_seconds(ip)
        context["locked_minutes"] = math.ceil(remaining / 60) if remaining else 0
        context["failed_attempts"] = failure_count(ip)
        context["max_attempts"] = settings.LOGIN_MAX_ATTEMPTS
        context["attempts_left"] = settings.LOGIN_MAX_ATTEMPTS - context["failed_attempts"]
        return context


def signup(request):
    site_settings = SiteSettings.get()

    if not site_settings.allow_registration:
        if request.method == "POST":
            return redirect("signup")
        return render(request, "account/signup.html", {"registration_allowed": False})

    if request.method == "POST":
        form = SignUpForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "اکانت شما با موفقیت ساخته شد. اکنون وارد شوید.")
            return redirect("login")
    else:
        form = SignUpForm()

    return render(
        request,
        "account/signup.html",
        {"form": form, "registration_allowed": True},
    )
