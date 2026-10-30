from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework.authtoken.views import obtain_auth_token
from rest_framework.routers import DefaultRouter

from . import api

app_name = "ai_datacenters"

router = DefaultRouter()
router.register("datacenters", api.DataCenterViewSet, basename="datacenter")

urlpatterns = [
    path("api/countries/at/", api.country_at, name="country-at"),
    path("api/countries/stats/", api.country_stats, name="country-stats"),
    path("api/filters/", api.filter_options, name="filter-options"),
    path("api/token/", obtain_auth_token, name="api-token"),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="ai_datacenters:schema"), name="docs"),
    path("api/", include(router.urls)),
]
