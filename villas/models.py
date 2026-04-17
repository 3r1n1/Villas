from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


def villa_thumbnail_path(instance, filename):
    return f"villas/covers/{instance.slug}_{filename}"


def room_photosphere_path(instance, filename):
    return f"villas/villa_{instance.villa_id}/rooms/{instance.pk}/photosphere_{filename}"


class Villa(models.Model):
    class PropertyType(models.TextChoices):
        VILLA = "villa", "Villa"
        APARTMENT = "apartment", "Apartment"
        HOUSE = "house", "House"
        TOWNHOUSE = "townhouse", "Townhouse"
        LAND = "land", "Land"
        COMMERCIAL = "commercial", "Commercial"
        OTHER = "other", "Other"

    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True)
    description = models.TextField(blank=True)
    address = models.CharField(max_length=300, blank=True)
    city = models.CharField(
        max_length=120,
        help_text="City (required for listings and search).",
    )
    zone = models.CharField(
        max_length=120,
        blank=True,
        help_text="Neighborhood, district, or zone.",
    )
    property_type = models.CharField(
        max_length=20,
        choices=PropertyType.choices,
        default=PropertyType.VILLA,
    )
    bedroom_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of bedrooms (for listings and filters).",
    )
    bathroom_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of bathrooms / toilets (WCs).",
    )
    has_garage = models.BooleanField(default=False)
    price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Display price (e.g. per night). Leave empty if not shown.",
    )
    thumbnail = models.ImageField(
        upload_to=villa_thumbnail_path,
        blank=True,
        null=True,
        help_text="Cover image for the villa (shown on listing and detail).",
    )
    is_published = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="villas_created",
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name

    def clean(self):
        super().clean()
        self.city = (self.city or "").strip()
        if not self.city:
            raise ValidationError({"city": "City is required."})


class Room(models.Model):
    villa = models.ForeignKey(Villa, on_delete=models.CASCADE, related_name="rooms")
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=0)
    photosphere = models.ImageField(
        upload_to=room_photosphere_path,
        blank=True,
        null=True,
        help_text="Equirectangular 360° panorama for the virtual tour (Street View style).",
    )
    is_entry = models.BooleanField(
        default=False,
        help_text="If checked, this room is where the tour starts (only one per villa recommended).",
    )

    class Meta:
        ordering = ["order", "pk"]

    def __str__(self):
        return f"{self.villa.name} — {self.name}"


class RoomHotspot(models.Model):
    """Clickable hotspot in one room's panorama that navigates to another room."""

    from_room = models.ForeignKey(
        Room,
        on_delete=models.CASCADE,
        related_name="hotspots_out",
    )
    to_room = models.ForeignKey(
        Room,
        on_delete=models.CASCADE,
        related_name="hotspots_in",
    )
    yaw = models.FloatField(help_text="Horizontal angle in degrees (Pannellum yaw).")
    pitch = models.FloatField(help_text="Vertical angle in degrees (Pannellum pitch).")
    label = models.CharField(max_length=200, blank=True, help_text="Optional label on the hotspot.")

    class Meta:
        ordering = ["from_room_id", "pk"]

    def clean(self):
        if self.from_room_id and self.to_room_id:
            if self.from_room_id == self.to_room_id:
                raise ValidationError("A hotspot cannot point to the same room.")
            if self.from_room.villa_id != self.to_room.villa_id:
                raise ValidationError("Hotspot must link to a room in the same villa.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.from_room.name} → {self.to_room.name}"


def room_image_path(instance, filename):
    return f"villas/villa_{instance.room.villa_id}/room_{instance.room_id}/{filename}"


class RoomImage(models.Model):
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to=room_image_path)
    caption = models.CharField(max_length=200, blank=True)
    is_360 = models.BooleanField(
        default=False,
        help_text="Legacy: prefer Room photosphere for tour. Use for optional flat gallery only.",
    )
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "pk"]

    def __str__(self):
        return f"{self.room} — {self.caption or 'Image'}"


class VillaAvailability(models.Model):
    """
    Staff-defined periods when the villa cannot be booked (maintenance, private use, etc.).
    """

    villa = models.ForeignKey(
        Villa, on_delete=models.CASCADE, related_name="availability_blocks"
    )
    start_date = models.DateField()
    end_date = models.DateField()
    note = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["-start_date", "pk"]
        verbose_name_plural = "Villa availability blocks"

    def __str__(self):
        return f"{self.villa.name}: {self.start_date} – {self.end_date}"

    def clean(self):
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValidationError("End date must be on or after start date.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


def _ranges_overlap(a_start, a_end, b_start, b_end):
    return a_start <= b_end and b_start <= a_end


class Booking(models.Model):
    villa = models.ForeignKey(Villa, on_delete=models.CASCADE, related_name="bookings")
    start_date = models.DateField()
    end_date = models.DateField()
    full_name = models.CharField(max_length=200)
    phone_number = models.CharField(max_length=40)
    is_confirmed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "pk"]

    def __str__(self):
        return f"{self.villa.name}: {self.start_date} – {self.end_date} ({self.full_name})"

    def clean(self):
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValidationError("End date must be on or after start date.")
        if not (self.villa_id and self.start_date and self.end_date):
            return
        others = Booking.objects.filter(villa_id=self.villa_id)
        if self.pk:
            others = others.exclude(pk=self.pk)
        for other in others:
            if _ranges_overlap(
                self.start_date, self.end_date, other.start_date, other.end_date
            ):
                raise ValidationError(
                    "These dates overlap an existing booking for this villa."
                )
        for block in VillaAvailability.objects.filter(villa_id=self.villa_id):
            if _ranges_overlap(
                self.start_date, self.end_date, block.start_date, block.end_date
            ):
                raise ValidationError(
                    "These dates overlap a period blocked by staff for this villa."
                )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
