from django.conf import settings
from django.db import models
from django.db.models import Q


class Message(models.Model):
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sent_messages",
        verbose_name="فرستنده",
    )
    receiver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="received_messages",
        null=True,
        blank=True,
        verbose_name="گیرنده",
    )
    group = models.ForeignKey(
        "ChatGroup",
        on_delete=models.CASCADE,
        related_name="messages",
        null=True,
        blank=True,
        verbose_name="گروه",
    )
    body = models.TextField(blank=True, verbose_name="متن پیام")
    file = models.FileField(
        upload_to="chat/%Y/%m/", blank=True, null=True, verbose_name="فایل پیوست"
    )
    file_name = models.CharField(max_length=255, blank=True, verbose_name="نام فایل")
    is_voice = models.BooleanField(default=False, verbose_name="پیام صوتی")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="زمان ارسال")
    is_read = models.BooleanField(default=False, verbose_name="خوانده‌شده")
    reply_to = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="replies",
        verbose_name="پاسخ به",
    )

    class Meta:
        ordering = ("created_at",)
        verbose_name = "پیام"
        verbose_name_plural = "پیام‌ها"
        indexes = [
            models.Index(fields=("sender", "receiver", "created_at")),
            models.Index(fields=("receiver", "is_read")),
            models.Index(fields=("group", "created_at")),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(receiver__isnull=False, group__isnull=True)
                | Q(receiver__isnull=True, group__isnull=False),
                name="message_exactly_one_target",
            )
        ]

    def __str__(self):
        target = self.group if self.group_id else self.receiver
        return f"{self.sender} → {target}: {self.body[:30]}"


class Mute(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="muted_chats",
        verbose_name="کاربر",
    )
    peer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="muted_by_users",
        verbose_name="طرف گفتگو",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="زمان بی‌صدا کردن")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("owner", "peer"), name="unique_mute_per_pair")
        ]
        verbose_name = "گفتگوی بی‌صدا"
        verbose_name_plural = "گفتگوهای بی‌صدا"

    def __str__(self):
        return f"{self.owner} ← بی‌صدا ← {self.peer}"


class MessageDeletion(models.Model):
    message = models.ForeignKey(
        Message,
        on_delete=models.CASCADE,
        related_name="hidden_by_users",
        verbose_name="پیام",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="hidden_messages",
        verbose_name="کاربر",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="زمان حذف")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("message", "user"), name="unique_hidden_message_per_user"
            )
        ]
        verbose_name = "پیام حذف‌شده"
        verbose_name_plural = "پیام‌های حذف‌شده"

    def __str__(self):
        return f"{self.user} پیام {self.message_id} را پنهان کرد"


class ChatGroup(models.Model):
    name = models.CharField(max_length=100, verbose_name="نام گروه")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="created_groups",
        verbose_name="سازنده",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="زمان ساخت")
    members = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        through="GroupMembership",
        related_name="chat_groups",
        verbose_name="اعضا",
    )

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "گروه"
        verbose_name_plural = "گروه‌ها"

    def __str__(self):
        return self.name


class GroupMembership(models.Model):
    group = models.ForeignKey(
        ChatGroup,
        on_delete=models.CASCADE,
        related_name="memberships",
        verbose_name="گروه",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="group_memberships",
        verbose_name="کاربر",
    )
    is_admin = models.BooleanField(default=False, verbose_name="مدیر")
    joined_at = models.DateTimeField(auto_now_add=True, verbose_name="زمان عضویت")
    last_seen_at = models.DateTimeField(
        null=True, blank=True, verbose_name="آخرین بازدید"
    )

    class Meta:
        ordering = ("joined_at",)
        constraints = [
            models.UniqueConstraint(fields=("group", "user"), name="unique_group_member")
        ]
        verbose_name = "عضو گروه"
        verbose_name_plural = "اعضای گروه"

    def __str__(self):
        return f"{self.user} در {self.group}"


class GroupMute(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="muted_groups",
        verbose_name="کاربر",
    )
    group = models.ForeignKey(
        ChatGroup,
        on_delete=models.CASCADE,
        related_name="muted_by",
        verbose_name="گروه",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="زمان بی‌صدا کردن")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("owner", "group"), name="unique_group_mute_per_user"
            )
        ]
        verbose_name = "گروه بی‌صدا"
        verbose_name_plural = "گروه‌های بی‌صدا"

    def __str__(self):
        return f"{self.owner} ← بی‌صدا ← {self.group}"
