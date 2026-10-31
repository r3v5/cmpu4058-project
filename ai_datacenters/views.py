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


# Plain-language help for the three measures, shown by the ⓘ buttons on
# the map page (one panel by the size toggles, one hint per filter range).
METRIC_HELP = {
    "power_mw": {
        "title": "IT Power (MW)",
        "text": "How much electricity the site's computing equipment (AI chips and servers) "
        "can draw at once. 1 MW is enough for about 800 homes; cooling comes on top.",
    },
    "capital_cost_busd": {
        "title": "Capital cost ($B)",
        "text": "Estimated money spent to build and equip the site: buildings, power and "
        "cooling, and the AI chips.",
    },
    "h100e": {
        "title": "H100 equivalents (H100e)",
        "text": "Computing power counted in Nvidia H100 chips. Other chips, such as Amazon "
        "Trainium or Google TPUs, are converted, so 500k H100e does as much AI work as 500,000 H100s.",
    },
}


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
        context["metric_help"] = METRIC_HELP
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
