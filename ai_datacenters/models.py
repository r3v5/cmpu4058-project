from django.contrib.gis.db import models
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator


class Country(models.Model):
    """A country boundary from Natural Earth (admin 0, 1:50m)."""

    name = models.CharField(max_length=100, unique=True)
    iso_a3 = models.CharField("ISO A3", max_length=3)
    geom = models.MultiPolygonField(srid=4326)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "countries"

    def __str__(self):
        return self.name


class DataCenter(models.Model):
    """An AI data center from the Epoch AI dataset, placed by geocoding.

    ``nearest_link`` and ``nearest_km`` are derived columns: a line to the
    closest other data center and its length. They are rewritten by
    ``spatial.recompute_nearest_links`` after every save and delete, because
    moving or removing one site can change another site's nearest neighbour.
    """

    class Precision(models.TextChoices):
        ADDRESS = "address", "Address"
        POSTCODE = "postcode", "Postcode"
        CITY = "city", "City"
        MANUAL = "manual", "Manual"

    name = models.CharField(max_length=200, unique=True)
    owner = models.CharField(max_length=100, db_index=True)
    users = models.TextField(blank=True, help_text="Comma-separated organisations using the site.")
    # Set in save() from the polygon that contains the location, so it
    # always matches the point, also after a site is moved in the admin.
    country = models.ForeignKey(
        Country,
        null=True,
        blank=True,
        editable=False,
        on_delete=models.SET_NULL,
        related_name="datacenters",
    )
    power_mw = models.FloatField("power (MW)", validators=[MinValueValidator(0)])
    capital_cost_busd = models.FloatField(
        "capital cost (2025 USD bn)", validators=[MinValueValidator(0)]
    )
    # Computing power in Nvidia H100-equivalents: Epoch AI converts every
    # chip type (A100, B200, TPU, ...) to how many H100s it matches.
    h100e = models.FloatField("H100 equivalents", validators=[MinValueValidator(0)], default=0)
    address = models.CharField(max_length=300, blank=True)
    location = models.PointField(srid=4326)
    geocode_precision = models.CharField(max_length=10, choices=Precision.choices)
    nearest_link = models.LineStringField(srid=4326, null=True, blank=True, editable=False)
    nearest_km = models.FloatField("nearest site (km)", null=True, blank=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def clean(self):
        if self.location and not (-180 <= self.location.x <= 180 and -90 <= self.location.y <= 90):
            raise ValidationError(
                {"location": "Longitude must be within ±180 and latitude within ±90."}
            )

    def save(self, *args, **kwargs):
        self.country = Country.objects.filter(geom__contains=self.location).first()
        super().save(*args, **kwargs)
        # Imported here: spatial.py imports this module.
        from .spatial import recompute_nearest_links

        recompute_nearest_links()
        # The recompute wrote this row's line with update(); load it so the
        # object (and the API response built from it) is up to date.
        self.refresh_from_db(fields=["nearest_link", "nearest_km"])

    def delete(self, *args, **kwargs):
        result = super().delete(*args, **kwargs)
        from .spatial import recompute_nearest_links

        recompute_nearest_links()
        return result
