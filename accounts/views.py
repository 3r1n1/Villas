from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.forms import AuthenticationForm
from django.shortcuts import redirect, render

from .forms import AdminUserCreationForm


def staff_required(view_func):
    """Decorator: user must be logged in and staff to access."""
    decorated = login_required(view_func)
    return user_passes_test(lambda u: u.is_staff, login_url="login")(decorated)


def superuser_required(view_func):
    """Decorator: user must be logged in and superuser to access."""
    decorated = login_required(view_func)
    return user_passes_test(
        lambda u: u.is_superuser, login_url="dashboard"
    )(decorated)


def home(request):
    return render(request, "accounts/home.html")


def login_view(request):
    if request.method == "POST":
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            if not user.is_staff:
                messages.error(
                    request,
                    "Only administrator accounts can log in here. Contact a superadmin to get an account.",
                )
                return render(request, "accounts/login.html", {"form": form})
            login(request, user)
            messages.success(request, "You are now logged in.")
            next_url = request.GET.get("next")
            return redirect(next_url or "dashboard")
    else:
        form = AuthenticationForm(request)

    return render(request, "accounts/login.html", {"form": form})


def logout_view(request):
    logout(request)
    messages.info(request, "You have been logged out.")
    return redirect("home")


@staff_required
def dashboard(request):
    from villas.models import Villa
    villas = Villa.objects.all()[:10]
    return render(request, "accounts/dashboard.html", {"villas": villas})


@superuser_required
def add_admin(request):
    """Only superadmins can create new admin accounts."""
    if request.method == "POST":
        form = AdminUserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "New administrator account has been created.")
            return redirect("dashboard")
    else:
        form = AdminUserCreationForm()

    return render(request, "accounts/add_admin.html", {"form": form})
