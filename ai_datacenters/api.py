"""REST API (controller layer for JSON). Pages live in views.py."""

import json

from django.contrib.gis.geos import Point
from django.db.models import Max, Min
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view
from rest_framework.exceptions import ValidationError
from rest_framework.request import Request
from rest_framework.response import Response

from . import spatial
from .filters import DataCenterFilter, country_choices, owner_choices
from .models import DataCenter
from .permissions import IsStaffOrReadOnly
from .serializers import (
    CountrySummarySerializer,
    DataCenterSerializer,
    NearestDataCenterSerializer,
    NearestQuerySerializer,
    PointQuerySerializer,
    WithinQuerySerializer,
)


def query_point(serializer_class: type[PointQuerySerializer], request: Request):
    """Validate query parameters; a bad value raises a 400 with field errors."""
    params = serializer_class(data=request.query_params)
    params.is_valid(raise_exception=True)
    data = params.validated_data
    return Point(data["lon"], data["lat"], srid=4326), data


def filtered_sites(request: Request):
    """The sites that match the list filters in the query string.

    Nearby searches take the same search and filter parameters as the list,
    so they only find the sites the map shows. A bad value is a 400.
    """
    filterset = DataCenterFilter(request.query_params, queryset=DataCenter.objects.all(), request=request)
    if not filterset.is_valid():
        raise ValidationError(filterset.errors)
    return filterset.qs


class DataCenterViewSet(viewsets.ModelViewSet):
    """CRUD for data centers as GeoJSON. Writes are staff-only."""

    queryset = DataCenter.objects.select_related("country")
    serializer_class = DataCenterSerializer
    permission_classes = [IsStaffOrReadOnly]
    filterset_class = DataCenterFilter

    @action(detail=False)
    def nearest(self, request: Request):
        """?lat=&lon=&n= — the n nearest sites, each with a line from the point.

        Also takes the list filters (owner, mw_min, search, ...).
        """
        point, params = query_point(NearestQuerySerializer, request)
        sites = spatial.nearest_datacenters(point, params["n"], filtered_sites(request))
        return Response(NearestDataCenterSerializer(sites, many=True, context={"point": point}).data)

    @action(detail=False)
    def within(self, request: Request):
        """?lat=&lon=&km= — sites within the radius, plus the buffer polygon.

        Also takes the list filters.
        """
        point, params = query_point(WithinQuerySerializer, request)
        sites = spatial.datacenters_within(point, params["km"], filtered_sites(request))
        buffer = spatial.buffer_polygon(point, params["km"])
        return Response({
            "buffer": json.loads(buffer.geojson),
            "sites": NearestDataCenterSerializer(sites, many=True, context={"point": point}).data,
        })


@api_view(["GET"])
def country_at(request: Request):
    """?lat=&lon= — the country containing the point and the sites inside it.

    Also takes the list filters; the totals count only the matching sites.
    """
    point, _ = query_point(PointQuerySerializer, request)
    matching = filtered_sites(request)
    country = spatial.country_at(point)
    if country is None:
        return Response({"detail": "No country at this point."}, status=status.HTTP_404_NOT_FOUND)
    sites = spatial.datacenters_in(country, matching)
    for key, value in spatial.country_totals(sites).items():
        setattr(country, key, value)
    return Response({
        "country": CountrySummarySerializer(country).data,
        "sites": DataCenterSerializer(sites, many=True).data,
    })


@api_view(["GET"])
def country_stats(request: Request):
    """Countries with at least one site and their totals (for the choropleth)."""
    return Response(CountrySummarySerializer(spatial.country_stats(), many=True).data)


@api_view(["GET"])
def filter_options(request: Request):
    """Values for the filter form: owners, countries and MW/cost/H100e ranges."""
    ranges = DataCenter.objects.aggregate(
        mw_min=Min("power_mw"), mw_max=Max("power_mw"),
        cost_min=Min("capital_cost_busd"), cost_max=Max("capital_cost_busd"),
        h100e_min=Min("h100e"), h100e_max=Max("h100e"),
    )
    return Response({
        "owners": list(owner_choices()),
        "countries": list(country_choices()),
        "power_mw": {"min": ranges["mw_min"], "max": ranges["mw_max"]},
        "capital_cost_busd": {"min": ranges["cost_min"], "max": ranges["cost_max"]},
        "h100e": {"min": ranges["h100e_min"], "max": ranges["h100e_max"]},
    })
