import math

from django import forms
from django.db.models import Q
from django_filters import rest_framework as filters

from . import spatial
from .models import Country, DataCenter


def owner_choices():
    """Distinct owner names, A to Z (filter form and /api/filters/)."""
    return DataCenter.objects.order_by("owner").values_list("owner", flat=True).distinct()


def country_choices():
    """Names of countries that have at least one site, A to Z."""
    return (
        Country.objects.filter(datacenters__isnull=False)
        .order_by("name")
        .values_list("name", flat=True)
        .distinct()
    )


class BBoxField(forms.CharField):
    """Parse "min_lon,min_lat,max_lon,max_lat" into four checked floats."""

    def clean(self, value):
        value = super().clean(value)
        if not value:
            return None
        parts = value.split(",")
        if len(parts) != 4:
            raise forms.ValidationError("Use four numbers: min_lon,min_lat,max_lon,max_lat.")
        try:
            bbox = tuple(float(part) for part in parts)
        except ValueError:
            raise forms.ValidationError("Every bbox value must be a number.") from None
        if not all(math.isfinite(number) for number in bbox):
            raise forms.ValidationError("Every bbox value must be a finite number.")
        min_lon, min_lat, max_lon, max_lat = bbox
        if not (-180 <= min_lon <= 180 and -180 <= max_lon <= 180):
            raise forms.ValidationError("Longitudes must be between -180 and 180.")
        if not (-90 <= min_lat <= 90 and -90 <= max_lat <= 90):
            raise forms.ValidationError("Latitudes must be between -90 and 90.")
        if min_lon >= max_lon or min_lat >= max_lat:
            raise forms.ValidationError("Each minimum must be smaller than its maximum.")
        return bbox


class BBoxFilter(filters.Filter):
    field_class = BBoxField


class DataCenterFilter(filters.FilterSet):
    """Query-string filters for the data center list (all bounds inclusive)."""

    # ?owner=Google&owner=Meta — choices are the owners in the database.
    owner = filters.AllValuesMultipleFilter(field_name="owner")
    country = filters.CharFilter(field_name="country__name")
    mw_min = filters.NumberFilter(field_name="power_mw", lookup_expr="gte")
    mw_max = filters.NumberFilter(field_name="power_mw", lookup_expr="lte")
    cost_min = filters.NumberFilter(field_name="capital_cost_busd", lookup_expr="gte")
    cost_max = filters.NumberFilter(field_name="capital_cost_busd", lookup_expr="lte")
    # ?search=texas — free text over site, owner, users, address and country.
    search = filters.CharFilter(method="filter_search")
    # ?bbox=min_lon,min_lat,max_lon,max_lat — only sites inside the box.
    bbox = BBoxFilter(method="filter_bbox")

    SEARCH_FIELDS = ("name", "owner", "users", "address", "country__name")

    class Meta:
        model = DataCenter
        fields = ["owner", "country", "mw_min", "mw_max", "cost_min", "cost_max", "search", "bbox"]

    def filter_search(self, queryset, name, value):
        matches = Q()
        for field in self.SEARCH_FIELDS:
            matches |= Q(**{f"{field}__icontains": value.strip()})
        return queryset.filter(matches)

    def filter_bbox(self, queryset, name, value):
        return spatial.in_bbox(queryset, value)
