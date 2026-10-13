"""Shared helpers for unread counts and channel-layer broadcasts."""
import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from django.utils import timezone

from .models import GroupMembership, GroupMute, Message, Mute

logger = logging.getLogger(__name__)


def conversation_group(user_a_id, user_b_id):
    first, second = sorted((int(user_a_id), int(user_b_id)))
    return f"chat_{first}_{second}"


def user_group(user_id):
    return f"user_{int(user_id)}"


def group_channel(group_id):
    return f"chatgroup_{int(group_id)}"


def _as_user_id(user):
    if user is None:
        return 0
    if isinstance(user, int):
        return user
    if getattr(user, "is_authenticated", False):
        return user.pk
    return 0


def unread_group_count(user):
    """My groups that hold at least one message I have not seen yet."""
    user_id = _as_user_id(user)
    if not user_id:
        return 0

    memberships = GroupMembership.objects.filter(user_id=user_id).values_list(
        "group_id", "last_seen_at"
    )
    unread = 0
    for group_id, seen_at in memberships:
        pending = Message.objects.filter(group_id=group_id).exclude(
            sender_id=user_id
        )
        if seen_at is not None:
            pending = pending.filter(created_at__gt=seen_at)
        if pending.exclude(hidden_by_users__user_id=user_id).exists():
            unread += 1
    return unread


def unread_chat_count(user):
    """Direct conversations plus groups holding at least one unread message.

    Accepts a user instance, a user id, or None.
    """
    receiver_id = _as_user_id(user)
    if not receiver_id:
        return 0
    direct = (
        Message.objects.filter(receiver_id=receiver_id, is_read=False)
        .exclude(hidden_by_users__user_id=receiver_id)
        .values("sender_id")
        .distinct()
        .count()
    )
    return direct + unread_group_count(receiver_id)


def is_muted(owner, peer):
    return Mute.objects.filter(owner=owner, peer=peer).exists()


def is_group_muted(owner, group):
    return GroupMute.objects.filter(owner=owner, group=group).exists()


def group_member_ids(group_id):
    return list(
        GroupMembership.objects.filter(group_id=group_id).values_list(
            "user_id", flat=True
        )
    )


def mark_group_seen(user_id, group_id):
    GroupMembership.objects.filter(user_id=user_id, group_id=group_id).update(
        last_seen_at=timezone.now()
    )


def _group_send(group, payload):
    try:
        channel_layer = get_channel_layer()
        if channel_layer is None:
            return
        async_to_sync(channel_layer.group_send)(group, payload)
    except Exception:
        logger.debug("channel layer send to %s failed", group, exc_info=True)


def group_send(channel_name, payload):
    """Broadcast an arbitrary event to a channel-layer group by name."""
    _group_send(channel_name, payload)


def build_badge_payload(user_id):
    return {"type": "notify.badge", "unread_chats": unread_chat_count(user_id)}


def build_read_payload(reader_id, peer_id, message_ids):
    """Tell the conversation that ``reader_id`` opened the given messages."""
    return {
        "type": "chat.read",
        "reader_id": int(reader_id),
        "message_ids": [int(pk) for pk in message_ids],
        "unread_chats": unread_chat_count(reader_id),
    }


def broadcast_badge(user_id, count=None):
    if user_id is None:
        return
    payload = build_badge_payload(user_id)
    if count is not None:
        payload["unread_chats"] = count
    _group_send(user_group(user_id), payload)


def broadcast_read(reader_id, peer_id, message_ids):
    message_ids = [int(pk) for pk in message_ids]
    if not message_ids:
        return
    _group_send(
        conversation_group(reader_id, peer_id),
        build_read_payload(reader_id, peer_id, message_ids),
    )


def broadcast_conversation_deleted(user_a_id, user_b_id):
    _group_send(
        conversation_group(user_a_id, user_b_id),
        {"type": "chat.conversation.deleted"},
    )


def _preview_of(body, file_name, fallback):
    preview = (body or "").strip().replace("\n", " ")
    return (preview or file_name or fallback)[:80]


def build_notify_message(sender, receiver, body, file_name=""):
    """Payload pushed to ``user_{receiver}`` when a direct message arrives."""
    return {
        "type": "notify.message",
        "kind": "dm",
        "peer_id": sender.pk,
        "peer_username": sender.get_username(),
        "preview": _preview_of(body, file_name, "پیام جدید"),
        "muted": is_muted(receiver, sender),
        "unread_chats": unread_chat_count(receiver),
    }


def build_group_notify_message(sender, group, viewer, body, file_name=""):
    """Payload pushed to ``user_{viewer}`` when a group message arrives.

    Mute state and the unread badge are per viewer, so the caller must build
    one payload per member instead of sharing a single dict.
    """
    return {
        "type": "notify.message",
        "kind": "group",
        "peer_id": group.pk,
        "peer_username": group.name,
        "preview": _preview_of(body, file_name, "پیام گروهی"),
        "muted": is_group_muted(viewer.pk, group),
        "unread_chats": unread_chat_count(viewer),
    }
