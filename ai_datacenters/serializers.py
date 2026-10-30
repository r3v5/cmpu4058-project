import json

from django.contrib.gis.geos import LineString
from rest_framework import serializers
from rest_framework_gis.serializers import GeoFeatureModelSerializer

from .models import Country, DataCenter


class DataCenterSerializer(GeoFeatureModelSerializer):
    """A data center as a GeoJSON Feature (Point), used for reads and writes."""

    country = serializers.SlugRelatedField(slug_field="name", read_only=True)

    class Meta:
        model = DataCenter
        geo_field = "location"
        fields = [
            "id", "name", "owner", "users", "country", "power_mw", "capital_cost_busd",
            "address", "geocode_precision", "nearest_link", "nearest_km",
        ]

    def validate_location(self, value):
        if not (-180 <= value.x <= 180 and -90 <= value.y <= 90):
            raise serializers.ValidationError("Longitude must be within ±180 and latitude within ±90.")
        return value


class NearestDataCenterSerializer(DataCenterSerializer):
    """Adds the distance from the query point and a line from it to the site."""

    distance_km = serializers.SerializerMethodField()
    link = serializers.SerializerMethodField()

    class Meta(DataCenterSerializer.Meta):
        fields = DataCenterSerializer.Meta.fields + ["distance_km", "link"]

    def get_distance_km(self, obj):
        return round(obj.distance.km, 2)

    def get_link(self, obj):
        line = LineString(self.context["point"], obj.location, srid=4326)
        return json.loads(line.geojson)


class CountrySummarySerializer(GeoFeatureModelSerializer):
    """A country polygon with totals for the sites inside it."""

    site_count = serializers.IntegerField(read_only=True)
    total_mw = serializers.FloatField(read_only=True)
    total_cost_busd = serializers.FloatField(read_only=True)

    class Meta:
        model = Country
        geo_field = "geom"
        fields = ["id", "name", "iso_a3", "site_count", "total_mw", "total_cost_busd"]


class PointQuerySerializer(serializers.Serializer):
    """Validates ?lat=&lon= (ported from week 5 parse_search_parameters)."""

    lat = serializers.FloatField(min_value=-90, max_value=90)
    lon = serializers.FloatField(min_value=-180, max_value=180)


class NearestQuerySerializer(PointQuerySerializer):
    n = serializers.IntegerField(min_value=1, max_value=20, default=5)


class WithinQuerySerializer(PointQuerySerializer):
    km = serializers.FloatField(max_value=5000)

    def validate_km(self, value):
        if value <= 0:
            raise serializers.ValidationError("Radius must be greater than 0 km.")
        return value
