from datetime import datetime
from pathlib import Path
import sqlite3
import tempfile

from django.conf import settings
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.http import Http404, HttpResponse
from django.urls import path
from django.utils.encoding import iri_to_uri

from .models import CumstomUserModel, SiteSettings


admin.site.site_header = "پنل مدیریت رها گیفت"
admin.site.site_title = "ادمین رها گیفت"
admin.site.index_title = "داشبورد مدیریت"


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    list_display = ("allow_registration",)

    def has_add_permission(self, request):
        return not SiteSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(CumstomUserModel)
class CustomUserAdmin(UserAdmin):
    list_display = (
        "username",
        "email",
        "first_name",
        "last_name",
        "is_staff",
        "is_superuser",
        "is_active",
        "date_joined",
    )
    search_fields = ("username", "email", "first_name", "last_name")
    ordering = ("username",)
    list_filter = ("is_staff", "is_superuser", "is_active", "date_joined")


def download_database(request):
    db_path = Path(settings.DATABASES["default"]["NAME"])
    if not db_path.is_absolute():
        db_path = settings.BASE_DIR / db_path

    if not db_path.exists():
        raise Http404("فایل دیتابیس پیدا نشد.")

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    filename = f"raha-gift-{stamp}.sqlite3"
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".sqlite3")
    tmp.close()
    tmp_path = Path(tmp.name)

    source = sqlite3.connect(str(db_path))
    destination = sqlite3.connect(str(tmp_path))
    try:
        source.backup(destination)
    finally:
        destination.close()
        source.close()

    data = tmp_path.read_bytes()
    tmp_path.unlink(missing_ok=True)

    response = HttpResponse(data, content_type="application/vnd.sqlite3")
    response["Content-Disposition"] = (
        f'attachment; filename="{iri_to_uri(filename)}"'
    )
    return response


_original_get_urls = admin.site.get_urls


def _get_urls():
    custom_urls = [
        path(
            "download-database/",
            admin.site.admin_view(download_database),
            name="download_database",
        ),
    ]
    return custom_urls + _original_get_urls()


admin.site.get_urls = _get_urls
