from django.urls import path

from . import views

urlpatterns = [
    # Staff
    path("manage/", views.villa_list_staff, name="villa_list_staff"),
    path("manage/add/", views.villa_add, name="villa_add"),
    path("manage/<slug:slug>/edit/", views.villa_edit, name="villa_edit"),
    path("manage/<slug:slug>/delete/", views.villa_delete, name="villa_delete"),
    path("manage/<slug:slug>/rooms/", views.villa_manage_rooms, name="villa_manage_rooms"),
    path("manage/room/<int:room_id>/delete/", views.room_delete, name="room_delete"),
    path("manage/room/<int:room_id>/edit/", views.room_edit, name="room_edit"),
    path("manage/room/<int:room_id>/hotspots/", views.room_hotspots, name="room_hotspots"),
    path("manage/room/<int:room_id>/images/add/", views.room_image_add, name="room_image_add"),
    path("manage/image/<int:image_id>/delete/", views.room_image_delete, name="room_image_delete"),
    # Public (specific paths before villa slug catch-all)
    path("", views.villa_list, name="villa_list"),
    path("<slug:slug>/tour/<int:room_id>/", views.villa_tour, name="villa_tour_room"),
    path("<slug:slug>/tour/", views.villa_tour, name="villa_tour"),
    path(
        "<slug:villa_slug>/room/<int:room_id>/",
        views.room_view_redirect,
        name="room_view",
    ),
    path(
        "<slug:slug>/booking/dates/",
        views.villa_booking_disabled_dates,
        name="villa_booking_disabled_dates",
    ),
    path(
        "<slug:slug>/booking/",
        views.villa_booking_create,
        name="villa_booking_create",
    ),
    path("<slug:slug>/", views.villa_detail, name="villa_detail"),
]
