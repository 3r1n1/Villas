from django.contrib import admin

from .models import Booking, Room, RoomHotspot, RoomImage, Villa, VillaAvailability


class VillaAvailabilityInline(admin.TabularInline):
    model = VillaAvailability
    extra = 0


@admin.register(Villa)
class VillaAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "city",
        "property_type",
        "bedroom_count",
        "bathroom_count",
        "has_garage",
        "price",
        "slug",
        "is_published",
        "created_at",
    )
    list_filter = ("is_published", "property_type", "city", "has_garage")
    search_fields = ("name", "city", "zone", "address", "slug")
    prepopulated_fields = {"slug": ("name",)}
    inlines = [VillaAvailabilityInline]


@admin.register(VillaAvailability)
class VillaAvailabilityAdmin(admin.ModelAdmin):
    list_display = ("villa", "start_date", "end_date", "note")
    list_filter = ("villa",)


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = (
        "villa",
        "start_date",
        "end_date",
        "full_name",
        "phone_number",
        "is_confirmed",
        "created_at",
    )
    list_editable = ("is_confirmed",)
    list_display_links = ("villa",)
    list_filter = ("villa", "is_confirmed", "start_date")
    search_fields = ("full_name", "phone_number", "villa__name")
    readonly_fields = ("created_at",)
    date_hierarchy = "start_date"


class RoomHotspotInline(admin.TabularInline):
    model = RoomHotspot
    fk_name = "from_room"
    extra = 0


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ("name", "villa", "order", "is_entry")
    list_filter = ("villa",)
    inlines = [RoomHotspotInline]


@admin.register(RoomHotspot)
class RoomHotspotAdmin(admin.ModelAdmin):
    list_display = ("from_room", "to_room", "yaw", "pitch")


@admin.register(RoomImage)
class RoomImageAdmin(admin.ModelAdmin):
    list_display = ("room", "caption", "is_360", "order")
