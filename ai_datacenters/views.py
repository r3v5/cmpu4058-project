"""HTML pages (controller layer for templates). The JSON API lives in api.py."""

from django.contrib.auth import login
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpRequest
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView, TemplateView

from .filters import country_choices, owner_choices
from .forms import SignupForm
from .models import DataCenter


class MapView(LoginRequiredMixin, TemplateView):
    """The main screen: filters, sites list, nearby search and the map.

    The filter choices are rendered on the server so the form works before
    any JavaScript has loaded; map.js then loads the sites from the API.
    """

    template_name = "map.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["owners"] = owner_choices()
        context["countries"] = country_choices()
        context["total"] = DataCenter.objects.count()
        return context


class SignupView(CreateView):
    """Anyone can create a regular account; they are logged in straight away."""

    form_class = SignupForm
    template_name = "registration/signup.html"
    success_url = reverse_lazy("ai_datacenters:map")

    def dispatch(self, request: HttpRequest, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect(self.success_url)
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form: SignupForm):
        response = super().form_valid(form)
        login(self.request, self.object)
        return response
