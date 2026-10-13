from pathlib import Path
from urllib.parse import urlencode
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.files.storage import default_storage
from django.db.models import OuterRef, Q, Subquery
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from .models import ChatGroup, GroupMembership, GroupMute, Message, Mute
from .presence import is_online
from .serializers import message_payload
from .services import (
    broadcast_badge,
    broadcast_conversation_deleted,
    broadcast_read,
    group_channel,
    group_member_ids,
    group_send,
    mark_group_seen,
)


def mark_conversation_read(me, other):
    """Flip unread flags and tell both sides (ticks + header badge)."""
    pending = Message.objects.filter(sender=other, receiver=me, is_read=False)
    ids = list(pending.values_list("id", flat=True))
    if not ids:
        return
    Message.objects.filter(pk__in=ids).update(is_read=True)
    broadcast_read(me.pk, other.pk, ids)
    broadcast_badge(me.pk)


@login_required
def inbox(request):
    User = get_user_model()
    me = request.user

    last_for_pair = (
        Message.objects.filter(
            Q(sender=me, receiver=OuterRef("pk"))
            | Q(sender=OuterRef("pk"), receiver=me)
        )
        .order_by("-created_at")
        .values("body", "created_at", "sender_id")[:1]
    )

    others = (
        User.objects.filter(is_active=True)
        .exclude(pk=me.pk)
        .annotate(
            last_body=Subquery(last_for_pair.values("body")[:1]),
            last_at=Subquery(last_for_pair.values("created_at")[:1]),
            last_sender_id=Subquery(last_for_pair.values("sender_id")[:1]),
        )
        .order_by("-last_at", "username")
    )

    muted_peers = set(
        Mute.objects.filter(owner=me).values_list("peer_id", flat=True)
    )

    users = []
    for user in others:
        unread = (
            Message.objects.filter(sender=user, receiver=me, is_read=False)
            .exclude(hidden_by_users__user=me)
            .count()
        )
        users.append(
            {
                "user": user,
                "unread": unread,
                "online": is_online(user.pk),
                "muted": user.pk in muted_peers,
                "last_body": user.last_body or "",
                "last_at": user.last_at,
            }
        )

    return render(
        request,
        "chat/inbox.html",
        {
            "users": users,
            "groups": inbox_groups(me),
            "new_group_users": list(
                User.objects.filter(is_active=True)
                .exclude(pk=me.pk)
                .order_by("username")
            ),
            "form_error": request.GET.get("error"),
        },
    )


def inbox_groups(me):
    """One row per group I belong to, newest conversation first."""
    muted = set(GroupMute.objects.filter(owner=me).values_list("group_id", flat=True))
    rows = []
    memberships = (
        GroupMembership.objects.filter(user=me)
        .select_related("group")
        .order_by("-group__created_at")
    )
    for membership in memberships:
        group = membership.group
        last = group.messages.order_by("-created_at").first()
        pending = group.messages.exclude(sender_id=me.pk)
        if membership.last_seen_at is not None:
            pending = pending.filter(created_at__gt=membership.last_seen_at)
        unread = pending.exclude(hidden_by_users__user=me).count()
        rows.append(
            {
                "group": group,
                "unread": unread,
                "muted": group.pk in muted,
                "is_admin": membership.is_admin,
                "member_count": group.members.count(),
                "last_body": (last.body if last else "") or "",
                "last_at": last.created_at if last else None,
            }
        )
    return rows


@login_required
def conversation(request, user_id):
    other = get_object_or_404(
        get_user_model().objects.filter(is_active=True), pk=user_id
    )
    if other.pk == request.user.pk:
        return redirect("chat:inbox")

    mark_conversation_read(request.user, other)

    return render(
        request,
        "chat/conversation.html",
        {
            "other": other,
            "other_online": is_online(other.pk),
            "other_muted": Mute.objects.filter(
                owner=request.user, peer=other
            ).exists(),
        },
    )


@login_required
def messages_api(request, user_id):
    other = get_object_or_404(
        get_user_model().objects.filter(is_active=True), pk=user_id
    )
    me = request.user

    mark_conversation_read(me, other)

    messages = (
        Message.objects.filter(
            Q(sender=me, receiver=other) | Q(sender=other, receiver=me)
        )
        .exclude(hidden_by_users__user=me)
        .select_related("sender", "reply_to__sender")
        .order_by("-created_at")[:100]
    )

    data = [message_payload(m) for m in reversed(list(messages))]
    return JsonResponse({"messages": data})


@login_required
def mute_api(request, user_id):
    if request.method != "POST":
        return JsonResponse({"error": "درخواست نامعتبر است."}, status=405)

    peer = get_object_or_404(
        get_user_model().objects.filter(is_active=True), pk=user_id
    )
    if peer.pk == request.user.pk:
        return JsonResponse({"error": "درخواست نامعتبر است."}, status=400)

    mute, created = Mute.objects.get_or_create(owner=request.user, peer=peer)
    if not created:
        mute.delete()
    return JsonResponse({"muted": created})


@login_required
def conversation_delete_api(request, user_id):
    """Wipe a direct thread from the inbox, where no chat socket is open."""
    if request.method != "POST":
        return JsonResponse({"error": "درخواست نامعتبر است."}, status=405)

    other = get_object_or_404(
        get_user_model().objects.filter(is_active=True), pk=user_id
    )
    me = request.user
    if other.pk == me.pk:
        return JsonResponse({"error": "درخواست نامعتبر است."}, status=400)

    deleted = Message.objects.filter(
        Q(sender=me, receiver=other) | Q(sender=other, receiver=me)
    ).delete()[0]

    broadcast_conversation_deleted(me.pk, other.pk)
    broadcast_badge(me.pk)
    broadcast_badge(other.pk)
    return JsonResponse({"deleted": deleted})


# --- گروه‌ها ---


def group_or_404(user, group_id):
    group = get_object_or_404(ChatGroup, pk=group_id)
    if not GroupMembership.objects.filter(group=group, user=user).exists():
        raise Http404
    return group


def membership_of(user, group):
    return GroupMembership.objects.get(group=group, user=user)


def broadcast_members(group_id):
    """Push the live member list so removed sockets close themselves."""
    group_send(
        group_channel(group_id),
        {"type": "chat.group.members", "member_ids": group_member_ids(group_id)},
    )


@login_required
def group_create(request):
    if request.method != "POST":
        return redirect("chat:inbox")

    def fail(message):
        return redirect(f"{reverse('chat:inbox')}?{urlencode({'error': message})}")

    name = (request.POST.get("name") or "").strip()
    if not name:
        return fail("نام گروه را وارد کنید.")
    if len(name) > 100:
        return fail("نام گروه بیش از حد مجاز است.")

    picked = set()
    for raw in request.POST.getlist("members"):
        try:
            picked.add(int(raw))
        except (TypeError, ValueError):
            continue
    picked.discard(request.user.pk)
    if not picked:
        return fail("حداقل یک عضو برای گروه انتخاب کنید.")

    confirmed = list(
        get_user_model()
        .objects.filter(pk__in=picked, is_active=True)
        .values_list("pk", flat=True)
    )
    if not confirmed:
        return fail("کاربر انتخاب‌شده معتبر نیست.")

    group = ChatGroup.objects.create(name=name, created_by=request.user)
    GroupMembership.objects.bulk_create(
        [GroupMembership(group=group, user_id=request.user.pk, is_admin=True)]
        + [GroupMembership(group=group, user_id=pk) for pk in confirmed]
    )
    return redirect("chat:group_conversation", group.pk)


@login_required
def group_conversation(request, group_id):
    group = group_or_404(request.user, group_id)
    membership = membership_of(request.user, group)
    mark_group_seen(request.user.pk, group.pk)

    members = [
        {
            "membership": row,
            "is_me": row.user_id == request.user.pk,
        }
        for row in group.memberships.select_related("user")
    ]
    addable = list(
        get_user_model()
        .objects.filter(is_active=True)
        .exclude(pk=request.user.pk)
        .exclude(group_memberships__group=group)
        .order_by("username")
    )

    return render(
        request,
        "chat/group.html",
        {
            "group": group,
            "is_admin": membership.is_admin,
            "member_count": group.members.count(),
            "members": members,
            "addable_users": addable,
            "group_muted": GroupMute.objects.filter(
                owner=request.user, group=group
            ).exists(),
        },
    )


@login_required
def group_messages_api(request, group_id):
    group = group_or_404(request.user, group_id)
    me = request.user
    mark_group_seen(me.pk, group.pk)

    messages = (
        group.messages.exclude(hidden_by_users__user=me)
        .select_related("sender", "reply_to__sender")
        .order_by("-created_at")[:100]
    )
    data = [
        message_payload(m, group_id=group.pk) for m in reversed(list(messages))
    ]
    return JsonResponse({"messages": data})


@login_required
def group_mute_api(request, group_id):
    if request.method != "POST":
        return JsonResponse({"error": "درخواست نامعتبر است."}, status=405)

    group = group_or_404(request.user, group_id)
    mute, created = GroupMute.objects.get_or_create(owner=request.user, group=group)
    if not created:
        mute.delete()
    return JsonResponse({"muted": created})


@login_required
def group_members_api(request, group_id):
    if request.method != "POST":
        return JsonResponse({"error": "درخواست نامعتبر است."}, status=405)

    group = group_or_404(request.user, group_id)
    if not membership_of(request.user, group).is_admin:
        return JsonResponse(
            {"error": "فقط مدیر گروه می‌تواند اعضا را تغییر دهد."}, status=403
        )

    if (request.POST.get("action") or "add") == "remove":
        error = remove_group_member(request, group)
    else:
        error = add_group_members(request, group)

    if error:
        return JsonResponse({"error": error}, status=400)

    broadcast_members(group.pk)
    return JsonResponse({"members": group_member_ids(group.pk)})


def add_group_members(request, group):
    picked = set()
    for raw in request.POST.getlist("members"):
        try:
            picked.add(int(raw))
        except (TypeError, ValueError):
            continue
    picked.discard(request.user.pk)
    if not picked:
        return "کاربری انتخاب نشده است."

    candidates = get_user_model().objects.filter(pk__in=picked, is_active=True)
    existing = set(
        group.memberships.values_list("user_id", flat=True)
    )
    created = [
        GroupMembership(group=group, user_id=user.pk)
        for user in candidates
        if user.pk not in existing
    ]
    if not created:
        return "این کاربران از قبل عضو گروه هستند."
    GroupMembership.objects.bulk_create(created)
    return None


def remove_group_member(request, group):
    try:
        target_id = int(request.POST.get("user_id") or 0)
    except (TypeError, ValueError):
        return "کاربر انتخاب‌شده معتبر نیست."

    target = group.memberships.filter(user_id=target_id).first()
    if target is None:
        return "این کاربر عضو گروه نیست."
    if target.user_id == request.user.pk:
        return "برای خروج از گروه از گزینهٔ «ترک گروه» استفاده کنید."
    if (
        target.is_admin
        and group.memberships.filter(is_admin=True).count() == 1
    ):
        return "گروه نمی‌تواند بدون مدیر بماند."

    target.delete()
    GroupMute.objects.filter(owner_id=target.user_id, group=group).delete()
    return None


@login_required
def group_leave_api(request, group_id):
    if request.method != "POST":
        return JsonResponse({"error": "درخواست نامعتبر است."}, status=405)

    group = group_or_404(request.user, group_id)
    membership = membership_of(request.user, group)
    if membership.is_admin and not group.memberships.filter(
        is_admin=True
    ).exclude(pk=membership.pk).exists():
        return JsonResponse(
            {"error": "شما تنها مدیر گروه هستید؛ ابتدا گروه را حذف کنید."},
            status=400,
        )

    membership.delete()
    GroupMute.objects.filter(owner=request.user, group=group).delete()
    broadcast_members(group.pk)
    broadcast_badge(request.user.pk)
    return JsonResponse({"left": True})


@login_required
def group_delete_api(request, group_id):
    if request.method != "POST":
        return JsonResponse({"error": "درخواست نامعتبر است."}, status=405)

    group = group_or_404(request.user, group_id)
    if not membership_of(request.user, group).is_admin:
        return JsonResponse(
            {"error": "فقط مدیر گروه می‌تواند گروه را حذف کند."}, status=403
        )

    members = group_member_ids(group.pk)
    channel = group_channel(group.pk)
    group.delete()

    group_send(channel, {"type": "chat.group.deleted"})
    for user_id in members:
        broadcast_badge(user_id)
    return JsonResponse({"deleted": True})


ALLOWED_UPLOAD_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp",
    ".pdf", ".zip", ".rar", ".7z",
    ".mp3", ".ogg", ".m4a", ".wav", ".webm",
    ".mp4",
    ".txt", ".md", ".csv", ".log", ".json",
    ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".rtf",
}

# فقط برای پسوندهای TEXT_EXTENSIONS پذیرفته می‌شود؛ برای بقیه رد است.
TEXT_EXTENSIONS = {".txt", ".md", ".csv", ".log", ".json"}

GENERIC_CONTENT_TYPES = {"application/octet-stream", "binary/octet-stream"}

ALLOWED_UPLOAD_CONTENT_TYPES = {
    "image/png", "image/jpeg", "image/gif", "image/webp",
    "application/pdf",
    "application/zip", "application/x-rar-compressed", "application/x-7z-compressed",
    "audio/mpeg", "audio/ogg", "audio/mp4", "audio/wav", "audio/x-wav", "audio/webm",
    "video/mp4", "video/webm",
    "text/plain", "text/markdown", "text/csv",
    "application/json", "application/msword",
    "application/vnd.ms-excel", "application/vnd.ms-powerpoint",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}

VOICE_CONTENT_TYPES = {"audio/mpeg", "audio/ogg", "audio/mp4", "audio/wav", "audio/x-wav", "audio/webm"}

MAX_UPLOAD_SIZE = 15 * 1024 * 1024


@login_required
def upload_api(request):
    if request.method != "POST":
        return JsonResponse({"error": "درخواست نامعتبر است."}, status=405)

    upload = request.FILES.get("file")
    if upload is None:
        return JsonResponse({"error": "فایلی ارسال نشده است."}, status=400)

    if upload.size > MAX_UPLOAD_SIZE:
        return JsonResponse({"error": "حجم فایل بیشتر از ۱۵ مگابایت است."}, status=400)

    extension = Path(upload.name or "").suffix.lower()
    if extension not in ALLOWED_UPLOAD_EXTENSIONS:
        return JsonResponse({"error": "نوع فایل مجاز نیست."}, status=400)

    content_type = (upload.content_type or "").lower()
    if content_type and content_type not in ALLOWED_UPLOAD_CONTENT_TYPES:
        generic_ok = (
            content_type in GENERIC_CONTENT_TYPES and extension in TEXT_EXTENSIONS
        )
        if not generic_ok:
            return JsonResponse({"error": "نوع فایل مجاز نیست."}, status=400)

    stored = default_storage.save(f"chat/{uuid4().hex}{extension}", upload)

    return JsonResponse(
        {
            "file": stored,
            "file_name": Path(upload.name).name[:255],
            "is_voice": content_type in VOICE_CONTENT_TYPES,
        }
    )
