import asyncio

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.contrib.auth import get_user_model
from django.core.files.storage import default_storage
from django.db.models import Q

from .models import ChatGroup, GroupMembership, Message, MessageDeletion
from .presence import add_connection, is_online, remove_connection, touch
from .serializers import message_payload
from .services import (
    build_badge_payload,
    build_group_notify_message,
    build_notify_message,
    build_read_payload,
    conversation_group,
    group_channel,
    group_member_ids,
    mark_group_seen,
    unread_chat_count,
    user_group,
)

MAX_MESSAGE_LENGTH = 2000
HEARTBEAT_SECONDS = 20
HEARTBEAT_GRACE_SECONDS = 5


@database_sync_to_async
def file_is_allowed(file_path):
    if not file_path:
        return True
    if not file_path.startswith("chat/"):
        return False
    return default_storage.exists(file_path)


def parse_reply_to(raw):
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


class ChatConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.user = self.scope["user"]
        if self.user.is_anonymous:
            await self.close(code=4001)
            return

        self.other_id = int(self.scope["url_route"]["kwargs"]["user_id"])
        if self.other_id == self.user.id:
            await self.close(code=4003)
            return

        if not await self.other_user_exists(self.other_id):
            await self.close(code=4004)
            return

        self.group = conversation_group(self.user.id, self.other_id)
        await self.channel_layer.group_add(self.group, self.channel_name)
        await self.accept()

        self._alive = True
        count = await database_sync_to_async(add_connection)(self.user.id)
        if count == 1:
            await self.channel_layer.group_send(
                self.group,
                {
                    "type": "presence",
                    "user_id": self.user.id,
                    "online": True,
                },
            )
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        await self._set_peer_online(await self.peer_is_online())

    async def disconnect(self, code):
        self._alive = False
        task = getattr(self, "_heartbeat_task", None)
        if task:
            task.cancel()
        group = getattr(self, "group", None)
        remaining = await database_sync_to_async(remove_connection)(self.user.id)
        if group:
            if remaining <= 0:
                await self.channel_layer.group_send(
                    group,
                    {
                        "type": "presence",
                        "user_id": self.user.id,
                        "online": False,
                    },
                )
            await self.channel_layer.group_discard(group, self.channel_name)

    async def receive_json(self, content, **kwargs):
        kind = content.get("type")

        if kind == "heartbeat":
            await database_sync_to_async(touch)(self.user.id)
            await self._set_peer_online(await self.peer_is_online())
            return

        if kind == "read":
            await self.mark_incoming_read()
            return

        if kind == "delete_message":
            await self.delete_message(
                content.get("id"), bool(content.get("for_everyone"))
            )
            return

        if kind == "delete_conversation":
            await self.delete_conversation()
            return

        body = (content.get("body") or "").strip()
        file_path = (content.get("file") or "").strip()
        file_name = (content.get("file_name") or "").strip()
        is_voice = bool(content.get("is_voice"))
        reply_to_id = parse_reply_to(content.get("reply_to"))

        if not body and not file_path:
            return

        if not await file_is_allowed(file_path):
            await self.send_json({"type": "error", "message": "فایل مجاز نیست."})
            return

        if reply_to_id is not None and not await self._valid_reply_to(reply_to_id):
            reply_to_id = None

        body = body[:MAX_MESSAGE_LENGTH]
        message, notify = await self.save_message(
            self.other_id, body, file_path, file_name, is_voice, reply_to_id
        )
        message["type"] = "chat.message"
        await self.channel_layer.group_send(self.group, message)
        await self.channel_layer.group_send(user_group(self.other_id), notify)

    async def chat_message(self, event):
        await self.send_json(event)

    async def chat_read(self, event):
        await self.send_json(event)

    async def chat_message_deleted(self, event):
        await self.send_json(event)

    async def chat_conversation_deleted(self, event):
        await self.send_json(event)

    async def presence(self, event):
        if event.get("user_id") == self.other_id:
            await self._set_peer_online(bool(event.get("online")))

    async def _set_peer_online(self, online):
        await self.send_json(
            {
                "type": "presence",
                "user_id": self.other_id,
                "online": bool(online),
            }
        )

    async def _heartbeat_loop(self):
        try:
            while self._alive:
                await asyncio.sleep(HEARTBEAT_SECONDS)
                await database_sync_to_async(touch)(self.user.id)
                await self._set_peer_online(await self.peer_is_online())
        except asyncio.CancelledError:
            pass

    # --- خواندن پیام‌ها ---

    async def mark_incoming_read(self):
        ids = await self._mark_incoming_read()
        if not ids:
            return
        payload = await database_sync_to_async(build_read_payload)(
            self.user.id, self.other_id, ids
        )
        await self.channel_layer.group_send(self.group, payload)
        badge = await database_sync_to_async(build_badge_payload)(self.user.id)
        await self.channel_layer.group_send(user_group(self.user.id), badge)

    @database_sync_to_async
    def _mark_incoming_read(self):
        pending = Message.objects.filter(
            sender_id=self.other_id, receiver_id=self.user.id, is_read=False
        )
        ids = list(pending.values_list("id", flat=True))
        if not ids:
            return []
        Message.objects.filter(pk__in=ids).update(is_read=True)
        return ids

    # --- حذف پیام و گفتگو ---

    async def delete_message(self, message_id, for_everyone):
        try:
            message_id = int(message_id)
        except (TypeError, ValueError):
            return

        result = await self._delete_message(message_id, for_everyone)
        if not result:
            return

        await self.channel_layer.group_send(self.group, result["event"])
        for user_id in (self.user.id, self.other_id):
            badge = await database_sync_to_async(build_badge_payload)(user_id)
            await self.channel_layer.group_send(user_group(user_id), badge)

    @database_sync_to_async
    def _delete_message(self, message_id, for_everyone):
        message = (
            Message.objects.filter(pk=message_id)
            .filter(
                Q(sender_id=self.user.id, receiver_id=self.other_id)
                | Q(sender_id=self.other_id, receiver_id=self.user.id)
            )
            .first()
        )
        if message is None:
            return None

        if for_everyone and message.sender_id != self.user.id:
            for_everyone = False

        if for_everyone:
            message.delete()
            event = {
                "type": "chat.message.deleted",
                "id": message_id,
                "for_everyone": True,
                "target_user_id": None,
            }
        else:
            MessageDeletion.objects.get_or_create(message=message, user=self.user)
            event = {
                "type": "chat.message.deleted",
                "id": message_id,
                "for_everyone": False,
                "target_user_id": self.user.id,
            }

        return {"event": event}

    async def delete_conversation(self):
        deleted = await self._delete_conversation()
        if not deleted:
            return
        await self.channel_layer.group_send(
            self.group, {"type": "chat.conversation.deleted"}
        )
        for user_id in (self.user.id, self.other_id):
            badge = await database_sync_to_async(build_badge_payload)(user_id)
            await self.channel_layer.group_send(user_group(user_id), badge)

    @database_sync_to_async
    def _delete_conversation(self):
        return (
            Message.objects.filter(
                Q(sender_id=self.user.id, receiver_id=self.other_id)
                | Q(sender_id=self.other_id, receiver_id=self.user.id)
            ).delete()[0]
            > 0
        )

    # --- سایر ---

    @database_sync_to_async
    def other_user_exists(self, user_id):
        return get_user_model().objects.filter(pk=user_id, is_active=True).exists()

    @database_sync_to_async
    def peer_is_online(self):
        return is_online(self.other_id)

    @database_sync_to_async
    def _valid_reply_to(self, message_id):
        return (
            Message.objects.filter(pk=message_id)
            .filter(
                Q(sender_id=self.user.id, receiver_id=self.other_id)
                | Q(sender_id=self.other_id, receiver_id=self.user.id)
            )
            .exists()
        )

    @database_sync_to_async
    def save_message(
        self, other_id, body, file_path, file_name, is_voice, reply_to_id=None
    ):
        receiver = get_user_model().objects.get(pk=other_id)
        message = Message.objects.create(
            sender=self.user,
            receiver=receiver,
            body=body,
            file=file_path or None,
            file_name=file_name[:255],
            is_voice=is_voice,
            reply_to_id=reply_to_id,
        )
        message = Message.objects.select_related("sender", "reply_to__sender").get(
            pk=message.pk
        )
        payload = message_payload(message)
        notify = build_notify_message(
            message.sender, receiver, message.body, message.file_name
        )
        return payload, notify


class GroupConsumer(AsyncJsonWebsocketConsumer):
    """Realtime socket bound to a single chat group."""

    async def connect(self):
        self.user = self.scope["user"]
        if self.user.is_anonymous:
            await self.close(code=4001)
            return

        self.group_id = int(self.scope["url_route"]["kwargs"]["group_id"])
        membership = await self.membership()
        if membership is None:
            await self.close(code=4004)
            return

        self.room = group_channel(self.group_id)
        await self.channel_layer.group_add(self.room, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        room = getattr(self, "room", None)
        if room:
            await self.channel_layer.group_discard(room, self.channel_name)

    async def receive_json(self, content, **kwargs):
        kind = content.get("type")

        if kind == "read":
            await self.mark_seen()
            return

        if kind == "delete_message":
            await self.delete_message(
                content.get("id"), bool(content.get("for_everyone"))
            )
            return

        if kind == "delete_conversation":
            await self.clear_for_me()
            return

        if not await self.still_member():
            await self.close(code=4005)
            return

        body = (content.get("body") or "").strip()
        file_path = (content.get("file") or "").strip()
        file_name = (content.get("file_name") or "").strip()
        is_voice = bool(content.get("is_voice"))
        reply_to_id = parse_reply_to(content.get("reply_to"))

        if not body and not file_path:
            return

        if not await file_is_allowed(file_path):
            await self.send_json({"type": "error", "message": "فایل مجاز نیست."})
            return

        if reply_to_id is not None and not await self._valid_reply_to(reply_to_id):
            reply_to_id = None

        body = body[:MAX_MESSAGE_LENGTH]
        payload, notifies = await self.save_message(
            body, file_path, file_name, is_voice, reply_to_id
        )
        payload["type"] = "chat.message"
        await self.channel_layer.group_send(self.room, payload)
        for viewer_id, notify in notifies:
            await self.channel_layer.group_send(user_group(viewer_id), notify)

    async def chat_message(self, event):
        await self.send_json(event)

    async def chat_message_deleted(self, event):
        await self.send_json(event)

    async def chat_group_members(self, event):
        if self.user.id not in (event.get("member_ids") or []):
            await self.close(code=4005)
            return
        await self.send_json(
            {"type": "group.members", "member_ids": event.get("member_ids") or []}
        )

    async def mark_seen(self):
        """Groups have no read ticks, so seeing them only refreshes the badge."""
        await database_sync_to_async(mark_group_seen)(self.user.id, self.group_id)
        badge = await database_sync_to_async(build_badge_payload)(self.user.id)
        await self.channel_layer.group_send(user_group(self.user.id), badge)

    async def delete_message(self, message_id, for_everyone):
        try:
            message_id = int(message_id)
        except (TypeError, ValueError):
            return
        result = await self._delete_message(message_id, for_everyone)
        if result is None:
            return
        await self.channel_layer.group_send(self.room, result)

    async def clear_for_me(self):
        cleared = await self._clear_for_me()
        if not cleared:
            return
        await self.send_json({"type": "chat.cleared_for_me"})
        badge = await database_sync_to_async(build_badge_payload)(self.user.id)
        await self.channel_layer.group_send(user_group(self.user.id), badge)

    @database_sync_to_async
    def membership(self):
        row = GroupMembership.objects.filter(
            group_id=self.group_id, user_id=self.user.id
        ).first()
        if row is None:
            return None
        return {"is_admin": bool(row.is_admin)}

    @database_sync_to_async
    def still_member(self):
        return GroupMembership.objects.filter(
            group_id=self.group_id, user_id=self.user.id
        ).exists()

    @database_sync_to_async
    def _delete_message(self, message_id, for_everyone):
        message = Message.objects.filter(
            pk=message_id, group_id=self.group_id
        ).first()
        if message is None:
            return None

        if for_everyone and message.sender_id != self.user.id:
            for_everyone = False

        if for_everyone:
            message.delete()
            return {
                "type": "chat.message.deleted",
                "id": message_id,
                "for_everyone": True,
                "target_user_id": None,
            }

        MessageDeletion.objects.get_or_create(message=message, user=self.user)
        return {
            "type": "chat.message.deleted",
            "id": message_id,
            "for_everyone": False,
            "target_user_id": self.user.id,
        }

    @database_sync_to_async
    def _clear_for_me(self):
        ids = list(
            Message.objects.filter(group_id=self.group_id)
            .exclude(hidden_by_users__user_id=self.user.id)
            .values_list("id", flat=True)
        )
        if not ids:
            return False
        MessageDeletion.objects.bulk_create(
            [MessageDeletion(message_id=pk, user=self.user) for pk in ids],
            ignore_conflicts=True,
        )
        return True

    @database_sync_to_async
    def _valid_reply_to(self, message_id):
        return Message.objects.filter(pk=message_id, group_id=self.group_id).exists()

    @database_sync_to_async
    def save_message(
        self, body, file_path, file_name, is_voice, reply_to_id=None
    ):
        group = ChatGroup.objects.get(pk=self.group_id)
        message = Message.objects.create(
            sender=self.user,
            receiver=None,
            group=group,
            body=body,
            file=file_path or None,
            file_name=file_name[:255],
            is_voice=is_voice,
            reply_to_id=reply_to_id,
        )
        message = Message.objects.select_related("sender", "reply_to__sender").get(
            pk=message.pk
        )
        payload = message_payload(message, group_id=group.pk)
        viewers = list(group.members.exclude(pk=self.user.pk))
        notifies = [
            (
                viewer.pk,
                build_group_notify_message(
                    message.sender, group, viewer, message.body, message.file_name
                ),
            )
            for viewer in viewers
        ]
        return payload, notifies


class NotifyConsumer(AsyncJsonWebsocketConsumer):
    """Site-wide socket: header badge + toast for messages in other chats."""

    async def connect(self):
        self.user = self.scope["user"]
        if self.user.is_anonymous:
            await self.close(code=4001)
            return

        self.group = user_group(self.user.id)
        await self.channel_layer.group_add(self.group, self.channel_name)
        await self.accept()
        count = await database_sync_to_async(unread_chat_count)(self.user.id)
        await self.send_json({"type": "notify.sync", "unread_chats": count})

    async def disconnect(self, code):
        group = getattr(self, "group", None)
        if group:
            await self.channel_layer.group_discard(group, self.channel_name)

    async def notify_badge(self, event):
        await self.send_json(
            {"type": "notify.badge", "unread_chats": event.get("unread_chats", 0)}
        )

    async def notify_message(self, event):
        await self.send_json(event)
