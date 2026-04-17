import logging
from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.db.models import Q
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from accounts.views import staff_required

from .booking_email import send_booking_notification
from .forms import (
    BookingForm,
    RoomForm,
    RoomHotspotFormSet,
    RoomImageForm,
    VillaForm,
    VillaSearchForm,
)
from .models import Room, RoomImage, Villa

logger = logging.getLogger(__name__)


def _get_entry_room(villa):
    """Tour starts here: explicit entry flag, then room named Entry, then first by order."""
    qs = villa.rooms.all()
    entry = qs.filter(is_entry=True).first()
    if entry:
        return entry
    entry = qs.filter(name__iexact="entry").first()
    if entry:
        return entry
    return qs.order_by("order", "pk").first()


def _first_room_with_photosphere(villa, preferred=None):
    """
    Pannellum firstScene must reference a scene with a non-empty panorama URL.
    Prefer `preferred` if it has a photosphere; else same entry rules among rooms with images.
    """
    qs = villa.rooms.order_by("order", "pk")
    if preferred is not None and preferred.photosphere:
        return preferred
    for room in qs.filter(is_entry=True):
        if room.photosphere:
            return room
    for room in qs.filter(name__iexact="entry"):
        if room.photosphere:
            return room
    for room in qs:
        if room.photosphere:
            return room
    return None


def _build_tour_config(request, villa, initial_room=None):
    """
    Pannellum multi-scene config + meta for History API.
    See https://pannellum.org/documentation/examples/tour/
    """
    rooms = list(
        villa.rooms.prefetch_related("hotspots_out__to_room").order_by("order", "pk")
    )
    if not rooms:
        return None

    scenes = {}
    for room in rooms:
        sid = f"room_{room.pk}"
        panorama_url = ""
        if room.photosphere:
            panorama_url = request.build_absolute_uri(room.photosphere.url)
        # Pannellum expects hotSpots as an array (it calls .sort / .forEach), not a JSON object.
        hot_spots = []
        for hs in room.hotspots_out.all():
            hot_spots.append(
                {
                    "id": f"hs_{hs.pk}",
                    "pitch": float(hs.pitch),
                    "yaw": float(hs.yaw),
                    "type": "scene",
                    "text": hs.label or hs.to_room.name,
                    "sceneId": f"room_{hs.to_room_id}",
                }
            )
        scenes[sid] = {
            "title": room.name,
            "panorama": panorama_url,
            "hotSpots": hot_spots,
        }

    first_room = _first_room_with_photosphere(villa, preferred=initial_room)
    if first_room is None:
        return None
    first_scene = f"room_{first_room.pk}"

    tour_prefix = reverse("villa_tour", kwargs={"slug": villa.slug})
    # Pannellum expects `scenes` on the top-level viewer config (same as official tour example),
    # not nested under `default`; otherwise k.scenes is undefined and no panorama is applied.
    return {
        "default": {
            "firstScene": first_scene,
            "sceneFadeDuration": 1000,
            "autoLoad": True,
        },
        "scenes": scenes,
        "meta": {
            "villaSlug": villa.slug,
            "entryRoomId": first_room.pk,
            "tourPathPrefix": tour_prefix,
        },
    }


# ---------- Public views ----------


def villa_list(request):
    base = Villa.objects.filter(is_published=True)
    cities = list(
        base.exclude(city="")
        .values_list("city", flat=True)
        .distinct()
        .order_by("city")
    )
    form = VillaSearchForm(request.GET or None, city_choices=cities)
    villas = base

    if form.is_valid():
        d = form.cleaned_data
        if d.get("q"):
            term = d["q"].strip()
            if term:
                villas = villas.filter(
                    Q(name__icontains=term)
                    | Q(description__icontains=term)
                    | Q(address__icontains=term)
                    | Q(city__icontains=term)
                    | Q(zone__icontains=term)
                )
        if d.get("city"):
            villas = villas.filter(city__iexact=d["city"])
        if d.get("zone"):
            z = d["zone"].strip()
            if z:
                villas = villas.filter(zone__icontains=z)
        if d.get("property_type"):
            villas = villas.filter(property_type=d["property_type"])
        if d.get("bedrooms_min") is not None:
            villas = villas.filter(bedroom_count__gte=d["bedrooms_min"])
        if d.get("bathrooms_min") is not None:
            villas = villas.filter(bathroom_count__gte=d["bathrooms_min"])
        garage = d.get("garage")
        if garage == "yes":
            villas = villas.filter(has_garage=True)
        elif garage == "no":
            villas = villas.filter(has_garage=False)
        if d.get("price_min") is not None:
            villas = villas.filter(price__gte=d["price_min"])
        if d.get("price_max") is not None:
            villas = villas.filter(price__lte=d["price_max"])

    return render(
        request,
        "villas/villa_list.html",
        {
            "villas": villas,
            "search_form": form,
            "villas_count": villas.count(),
        },
    )


def villa_detail(request, slug):
    villa = get_object_or_404(Villa, slug=slug, is_published=True)
    has_tour = villa.rooms.exists()
    return render(
        request,
        "villas/villa_detail.html",
        {
            "villa": villa,
            "has_tour": has_tour,
            "booking_form": BookingForm(villa=villa),
        },
    )


def room_view_redirect(request, villa_slug, room_id):
    """Legacy URL; tour is the only public room experience."""
    return redirect("villa_tour_room", slug=villa_slug, room_id=room_id)


def villa_tour(request, slug, room_id=None):
    villa = get_object_or_404(Villa, slug=slug, is_published=True)
    rooms = villa.rooms.all()
    if not rooms.exists():
        raise Http404("No rooms for this villa.")

    initial_room = None
    if room_id is not None:
        initial_room = get_object_or_404(Room, villa=villa, pk=room_id)

    tour_config = _build_tour_config(request, villa, initial_room=initial_room)
    if tour_config is None:
        raise Http404("Tour unavailable.")

    first_room = _first_room_with_photosphere(
        villa, preferred=initial_room if room_id is not None else None
    )
    return render(
        request,
        "villas/villa_tour.html",
        {
            "villa": villa,
            "tour_config": tour_config,
            "room": first_room,
            "room_panorama_absolute": request.build_absolute_uri(first_room.photosphere.url),
        },
    )


# ---------- Staff views ----------


@staff_required
def villa_list_staff(request):
    villas = Villa.objects.all()
    return render(request, "villas/villa_list_staff.html", {"villas": villas})


@staff_required
def villa_add(request):
    if request.method == "POST":
        form = VillaForm(request.POST, request.FILES)
        if form.is_valid():
            villa = form.save(commit=False)
            villa.created_by = request.user
            villa.save()
            messages.success(request, f"Villa '{villa.name}' created.")
            return redirect("villa_manage_rooms", slug=villa.slug)
    else:
        form = VillaForm()
    return render(request, "villas/villa_form.html", {"form": form, "title": "Add villa"})


@staff_required
def villa_edit(request, slug):
    villa = get_object_or_404(Villa, slug=slug)
    if request.method == "POST":
        form = VillaForm(request.POST, request.FILES, instance=villa)
        if form.is_valid():
            form.save()
            messages.success(request, "Villa updated.")
            return redirect("villa_manage_rooms", slug=villa.slug)
    else:
        form = VillaForm(instance=villa)
    return render(
        request, "villas/villa_form.html", {"form": form, "villa": villa, "title": "Edit villa"}
    )


@staff_required
def villa_manage_rooms(request, slug):
    villa = get_object_or_404(Villa, slug=slug)
    if request.method == "POST":
        form = RoomForm(request.POST, request.FILES)
        if form.is_valid():
            room = form.save(commit=False)
            room.villa = villa
            room.save()
            messages.success(request, f"Room '{room.name}' created.")
            return redirect("villa_manage_rooms", slug=slug)
    else:
        form = RoomForm(initial={"order": villa.rooms.count()})
    rooms = villa.rooms.all()
    return render(
        request,
        "villas/villa_manage_rooms.html",
        {"villa": villa, "rooms": rooms, "form": form},
    )


@staff_required
def villa_delete(request, slug):
    villa = get_object_or_404(Villa, slug=slug)
    if request.method == "POST":
        villa_name = villa.name
        villa.delete()
        messages.success(request, f"Villa '{villa_name}' deleted.")
        return redirect("villa_list_staff")
    return render(request, "villas/villa_confirm_delete.html", {"villa": villa})


@staff_required
def room_delete(request, room_id):
    room = get_object_or_404(Room, pk=room_id)
    villa_slug = room.villa.slug
    room_name = room.name
    if request.method == "POST":
        room.delete()
        messages.success(request, f"Room '{room_name}' deleted.")
    return redirect("villa_manage_rooms", slug=villa_slug)


@staff_required
def room_edit(request, room_id):
    room = get_object_or_404(Room, pk=room_id)
    if request.method == "POST":
        form = RoomForm(request.POST, request.FILES, instance=room)
        if form.is_valid():
            form.save()
            messages.success(request, "Room updated.")
            return redirect("villa_manage_rooms", slug=room.villa.slug)
    else:
        form = RoomForm(instance=room)
    return render(request, "villas/room_form.html", {"form": form, "room": room})


@staff_required
def room_hotspots(request, room_id):
    room = get_object_or_404(Room, pk=room_id)
    if request.method == "POST":
        formset = RoomHotspotFormSet(request.POST, instance=room)
        if formset.is_valid():
            formset.save()
            messages.success(request, "Hotspots saved.")
            return redirect("room_hotspots", room_id=room.pk)
    else:
        formset = RoomHotspotFormSet(instance=room)
    return render(
        request,
        "villas/room_hotspots.html",
        {"room": room, "formset": formset},
    )


@staff_required
def room_image_add(request, room_id):
    room = get_object_or_404(Room, pk=room_id)
    if request.method == "POST":
        form = RoomImageForm(request.POST, request.FILES)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.room = room
            obj.save()
            messages.success(request, "Image added.")
            return redirect("villa_manage_rooms", slug=room.villa.slug)
    else:
        form = RoomImageForm(initial={"order": room.images.count()})
    return render(request, "villas/room_image_form.html", {"form": form, "room": room})


@staff_required
def room_image_delete(request, image_id):
    if request.method != "POST":
        return redirect("villa_list_staff")
    image = get_object_or_404(RoomImage, pk=image_id)
    slug = image.room.villa.slug
    image.delete()
    messages.success(request, "Image removed.")
    return redirect("villa_manage_rooms", slug=slug)


def _disabled_date_strings_for_villa(villa):
    out = set()
    for b in villa.bookings.all():
        d = b.start_date
        while d <= b.end_date:
            out.add(d.isoformat())
            d += timedelta(days=1)
    for block in villa.availability_blocks.all():
        d = block.start_date
        while d <= block.end_date:
            out.add(d.isoformat())
            d += timedelta(days=1)
    return sorted(out)


@require_GET
def villa_booking_disabled_dates(request, slug):
    villa = get_object_or_404(Villa, slug=slug, is_published=True)
    return JsonResponse({"disabled": _disabled_date_strings_for_villa(villa)})


@require_POST
def villa_booking_create(request, slug):
    villa = get_object_or_404(Villa, slug=slug, is_published=True)
    form = BookingForm(request.POST, villa=villa)
    accept = request.headers.get("Accept", "")
    if form.is_valid():
        booking = form.save()
        email_ok, email_smtp, email_err = send_booking_notification(booking)

        if "application/json" in accept:
            payload = {
                "ok": True,
                "email_sent": email_ok,
                "email_smtp": email_smtp,
            }
            if email_ok and not email_smtp:
                payload["info"] = (
                    "Your request is saved. Email appeared only in the server console "
                    "(not your inbox). For real email, add EMAIL_HOST_PASSWORD to a .env file "
                    "next to manage.py. A copy is also in booking_notifications.log."
                )
            elif not email_ok:
                payload["warning"] = (
                    (email_err or "Email could not be sent.")
                    + " Staff can read booking_notifications.log in the project folder."
                )
            return JsonResponse(payload)

        if not email_ok:
            messages.warning(
                request,
                "Your booking was saved. The notification email failed — see "
                "booking_notifications.log in the project folder, or fix SMTP settings.",
            )
            return redirect("villa_detail", slug=slug)
        if not email_smtp:
            messages.info(
                request,
                "Booking saved. Real email was not sent (SMTP not configured); "
                "check the server console or booking_notifications.log.",
            )
            return redirect("villa_detail", slug=slug)
        messages.success(
            request,
            "Your booking request has been received. We will contact you shortly.",
        )
        return redirect("villa_detail", slug=slug)
    if "application/json" in accept:
        return JsonResponse({"ok": False, "errors": form.errors}, status=400)
    messages.error(request, "Could not save your booking. Please check the form and try again.")
    return redirect("villa_detail", slug=slug)
