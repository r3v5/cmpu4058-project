from django_filters import rest_framework as filters

from .models import DataCenter


class DataCenterFilter(filters.FilterSet):
    """Query-string filters for the data center list (all bounds inclusive)."""

    # ?owner=Google&owner=Meta — choices are the owners in the database.
    owner = filters.AllValuesMultipleFilter(field_name="owner")
    country = filters.CharFilter(field_name="country__name")
    mw_min = filters.NumberFilter(field_name="power_mw", lookup_expr="gte")
    mw_max = filters.NumberFilter(field_name="power_mw", lookup_expr="lte")
    cost_min = filters.NumberFilter(field_name="capital_cost_busd", lookup_expr="gte")
    cost_max = filters.NumberFilter(field_name="capital_cost_busd", lookup_expr="lte")

    class Meta:
        model = DataCenter
        fields = ["owner", "country", "mw_min", "mw_max", "cost_min", "cost_max"]
