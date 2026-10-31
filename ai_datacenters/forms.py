from django.contrib.auth.forms import AuthenticationForm, UserCreationForm


class BootstrapFormMixin:
    """Give every input Bootstrap's form-control class."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")


class LoginForm(BootstrapFormMixin, AuthenticationForm):
    error_messages = {
        **AuthenticationForm.error_messages,
        "invalid_login": "Username or password is incorrect.",
    }


class SignupForm(BootstrapFormMixin, UserCreationForm):
    """Creates a regular (non-staff) account."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Short help texts instead of Django's long HTML list.
        self.fields["username"].help_text = "Letters, digits and @ . + - _ only."
        self.fields["password1"].help_text = "At least 8 characters, not only numbers."
        self.fields["password2"].help_text = ""
