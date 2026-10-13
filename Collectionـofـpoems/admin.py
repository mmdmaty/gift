from django.contrib import admin
from .models import Poem, PoemSounds


class PoemSoundsInline(admin.TabularInline):
    model = PoemSounds
    extra = 1


@admin.register(Poem)
class PoemAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "about",
        "author",
        "created_at",
    )
    search_fields = (
        "name",
        "text",
        "author__username",
        "about__username",
    )
    list_filter = ("created_at", "author")
    ordering = ("-created_at",)
    readonly_fields = ("created_at",)
    autocomplete_fields = ("about", "author")
    inlines = [PoemSoundsInline]


@admin.register(PoemSounds)
class PoemSoundsAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "poem",
        "sound",
    )
    search_fields = ("poem__name",)
    list_filter = ("poem",)
    autocomplete_fields = ("poem",)
