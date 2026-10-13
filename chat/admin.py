from django.contrib import admin

from .models import (
    ChatGroup,
    GroupMembership,
    GroupMute,
    Message,
    MessageDeletion,
    Mute,
)


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = (
        "sender",
        "receiver",
        "created_at",
        "is_read",
        "is_voice",
        "has_file",
        "body_preview",
    )
    search_fields = ("body", "file_name", "sender__username", "receiver__username")
    list_filter = ("is_read", "is_voice", "created_at")
    ordering = ("-created_at",)
    readonly_fields = (
        "sender",
        "receiver",
        "body",
        "file",
        "file_name",
        "is_voice",
        "created_at",
        "is_read",
    )

    @admin.display(description="متن", boolean=False)
    def body_preview(self, obj):
        return obj.body[:60] if obj.body else ("پیام صوتی" if obj.is_voice else "بدون متن")

    @admin.display(description="فایل", boolean=True)
    def has_file(self, obj):
        return bool(obj.file)


@admin.register(Mute)
class MuteAdmin(admin.ModelAdmin):
    list_display = ("owner", "peer", "created_at")
    search_fields = ("owner__username", "peer__username")
    ordering = ("-created_at",)


@admin.register(MessageDeletion)
class MessageDeletionAdmin(admin.ModelAdmin):
    list_display = ("message", "user", "created_at")
    search_fields = ("user__username", "message__body")
    ordering = ("-created_at",)


class GroupMembershipInline(admin.TabularInline):
    model = GroupMembership
    extra = 0
    readonly_fields = ("joined_at", "last_seen_at")


@admin.register(ChatGroup)
class ChatGroupAdmin(admin.ModelAdmin):
    list_display = ("name", "created_by", "created_at", "member_count")
    search_fields = ("name", "created_by__username")
    ordering = ("-created_at",)
    inlines = (GroupMembershipInline,)

    @admin.display(description="اعضا")
    def member_count(self, obj):
        return obj.members.count()


@admin.register(GroupMembership)
class GroupMembershipAdmin(admin.ModelAdmin):
    list_display = ("group", "user", "is_admin", "joined_at", "last_seen_at")
    list_filter = ("is_admin",)
    search_fields = ("group__name", "user__username")
    ordering = ("joined_at",)


@admin.register(GroupMute)
class GroupMuteAdmin(admin.ModelAdmin):
    list_display = ("owner", "group", "created_at")
    search_fields = ("owner__username", "group__name")
    ordering = ("-created_at",)
