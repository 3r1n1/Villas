from django import forms
from django.forms.models import BaseInlineFormSet, inlineformset_factory

from .models import Booking, Room, RoomHotspot, RoomImage, Villa


class VillaForm(forms.ModelForm):
    class Meta:
        model = Villa
        fields = (
            "name",
            "slug",
            "property_type",
            "city",
            "zone",
            "address",
            "bedroom_count",
            "bathroom_count",
            "has_garage",
            "price",
            "description",
            "thumbnail",
            "is_published",
        )


class VillaSearchForm(forms.Form):
    q = forms.CharField(
        required=False,
        label="Search",
        widget=forms.TextInput(
            attrs={
                "placeholder": "Search name, address, city, zone…",
                "class": "villa-search-input",
            }
        ),
    )
    city = forms.ChoiceField(required=False, label="City")
    zone = forms.CharField(
        required=False,
        label="Zone",
        widget=forms.TextInput(attrs={"placeholder": "Neighborhood / zone"}),
    )
    property_type = forms.ChoiceField(required=False, label="Type of real estate")
    bedrooms_min = forms.IntegerField(
        required=False,
        min_value=0,
        label="Min. bedrooms",
        widget=forms.NumberInput(attrs={"min": 0, "placeholder": "Any"}),
    )
    bathrooms_min = forms.IntegerField(
        required=False,
        min_value=0,
        label="Min. bathrooms / WCs",
        widget=forms.NumberInput(attrs={"min": 0, "placeholder": "Any"}),
    )
    garage = forms.ChoiceField(
        required=False,
        label="Garage",
        choices=[
            ("", "Any"),
            ("yes", "Yes"),
            ("no", "No"),
        ],
    )
    price_min = forms.DecimalField(
        required=False,
        min_value=0,
        label="Min. price",
        max_digits=12,
        decimal_places=2,
        widget=forms.NumberInput(attrs={"min": 0, "step": "0.01", "placeholder": "Any"}),
    )
    price_max = forms.DecimalField(
        required=False,
        min_value=0,
        label="Max. price",
        max_digits=12,
        decimal_places=2,
        widget=forms.NumberInput(attrs={"min": 0, "step": "0.01", "placeholder": "Any"}),
    )

    def __init__(self, *args, city_choices=None, **kwargs):
        super().__init__(*args, **kwargs)
        city_opts = [("", "Any city")]
        if city_choices:
            city_opts += [(c, c) for c in city_choices]
        self.fields["city"].choices = city_opts
        type_opts = [("", "Any type")] + list(Villa.PropertyType.choices)
        self.fields["property_type"].choices = type_opts
        for fname in ("city", "property_type", "garage"):
            self.fields[fname].widget.attrs.setdefault("class", "filter-select")
        for fname in ("bedrooms_min", "bathrooms_min", "price_min", "price_max"):
            self.fields[fname].widget.attrs.setdefault("class", "filter-input")

    def clean(self):
        cleaned = super().clean()
        pmin, pmax = cleaned.get("price_min"), cleaned.get("price_max")
        if pmin is not None and pmax is not None and pmin > pmax:
            self.add_error(
                "price_max",
                "Max price must be greater than or equal to min price.",
            )
        return cleaned


class RoomForm(forms.ModelForm):
    class Meta:
        model = Room
        fields = ("name", "description", "order", "photosphere", "is_entry")


class RoomImageForm(forms.ModelForm):
    class Meta:
        model = RoomImage
        fields = ("image", "caption", "is_360", "order")


class RoomHotspotForm(forms.ModelForm):
    class Meta:
        model = RoomHotspot
        fields = ("to_room", "yaw", "pitch", "label")

    def __init__(self, *args, parent_room=None, **kwargs):
        parent_room = kwargs.pop("parent_room", None) or parent_room
        super().__init__(*args, **kwargs)
        if parent_room is not None:
            self.fields["to_room"].queryset = Room.objects.filter(
                villa=parent_room.villa
            ).exclude(pk=parent_room.pk)


class HotspotInlineFormSet(BaseInlineFormSet):
    def _construct_form(self, i, **kwargs):
        kwargs["parent_room"] = self.instance
        return super()._construct_form(i, **kwargs)


RoomHotspotFormSet = inlineformset_factory(
    Room,
    RoomHotspot,
    form=RoomHotspotForm,
    formset=HotspotInlineFormSet,
    fk_name="from_room",
    extra=1,
    can_delete=True,
)


class BookingForm(forms.ModelForm):
    class Meta:
        model = Booking
        fields = ("start_date", "end_date", "full_name", "phone_number")
        widgets = {
            "start_date": forms.HiddenInput(),
            "end_date": forms.HiddenInput(),
            "full_name": forms.TextInput(
                attrs={"autocomplete": "name", "placeholder": "Your full name"}
            ),
            "phone_number": forms.TextInput(
                attrs={"autocomplete": "tel", "placeholder": "Phone number"}
            ),
        }

    def __init__(self, *args, villa=None, **kwargs):
        self.villa = villa
        super().__init__(*args, **kwargs)
        if villa is not None:
            self.instance.villa = villa

    def save(self, commit=True):
        if self.villa is not None:
            self.instance.villa = self.villa
        return super().save(commit=commit)
