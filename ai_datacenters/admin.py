from django.contrib import admin
from django.contrib.gis.admin import GISModelAdmin
from django.db.models import QuerySet
from django.http import HttpRequest

from .models import Country, DataCenter
from .spatial import recompute_nearest_links


@admin.register(DataCenter)
class DataCenterAdmin(GISModelAdmin):
    list_display = ("name", "owner", "country", "power_mw", "capital_cost_busd", "geocode_precision", "nearest_km")
    list_filter = ("owner", "country", "geocode_precision")
    search_fields = ("name", "owner", "users", "address")
    readonly_fields = ("country", "nearest_km", "created_at", "updated_at")

    def delete_queryset(self, request: HttpRequest, queryset: QuerySet[DataCenter]):
        # Bulk delete bypasses DataCenter.delete(), so refresh links here.
        super().delete_queryset(request, queryset)
        recompute_nearest_links()


@admin.register(Country)
class CountryAdmin(GISModelAdmin):
    list_display = ("name", "iso_a3")
    search_fields = ("name", "iso_a3")
