from django.contrib.auth.forms import UserCreationForm

from .models import CumstomUserModel


class SignUpForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = CumstomUserModel
        fields = ("username",)
