from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User


class AdminUserCreationForm(UserCreationForm):
    """Form for superadmins to create new admin users. New users get is_staff=True."""

    is_superuser = forms.BooleanField(
        required=False,
        initial=False,
        label="Superadmin (can add other admins)",
        help_text="If checked, this admin can create more admin accounts.",
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "password1", "password2", "is_superuser")

    def save(self, commit=True):
        user = super().save(commit=False)
        user.is_staff = True  # Always staff so they can log in and see admin area
        user.is_superuser = self.cleaned_data.get("is_superuser", False)
        if commit:
            user.save()
        return user
