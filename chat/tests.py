import asyncio
from datetime import timedelta
from pathlib import Path

from channels.testing import WebsocketCommunicator
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core.cache import cache
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, TransactionTestCase
from django.urls import reverse

from .consumers import ChatConsumer, GroupConsumer, NotifyConsumer
from .models import (
    ChatGroup,
    GroupMembership,
    GroupMute,
    Message,
    MessageDeletion,
    Mute,
)
from .presence import add_connection, is_online, remove_connection, touch
from .services import unread_chat_count


class ChatViewsTests(TestCase):
    def setUp(self):
        cache.clear()
        User = get_user_model()
        self.alice = User.objects.create_user("alice", password="Qu1et-River-88x")
        self.bob = User.objects.create_user("bob", password="Qu1et-River-88x")

    def tearDown(self):
        cache.clear()

    def test_inbox_requires_login(self):
        response = self.client.get(reverse("chat:inbox"))
        self.assertEqual(response.status_code, 302)

    def test_inbox_lists_other_users(self):
        self.client.login(username="alice", password="Qu1et-River-88x")
        response = self.client.get(reverse("chat:inbox"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "bob")

    def test_inbox_excludes_self(self):
        self.client.login(username="alice", password="Qu1et-River-88x")
        response = self.client.get(reverse("chat:inbox"))
        self_url = reverse("chat:conversation", args=[self.alice.pk])
        self.assertNotContains(response, self_url)

    def test_inbox_shows_peer_online_dot(self):
        add_connection(self.bob.pk)
        self.client.login(username="alice", password="Qu1et-River-88x")
        response = self.client.get(reverse("chat:inbox"))
        self.assertContains(response, "chat-dot is-online")

    def test_inbox_page_view_alone_does_not_mark_online(self):
        self.client.login(username="alice", password="Qu1et-River-88x")
        self.client.get(reverse("chat:inbox"))
        self.assertFalse(is_online(self.alice.pk))

    def test_conversation_marks_messages_read(self):
        Message.objects.create(sender=self.bob, receiver=self.alice, body="سلام")
        self.client.login(username="alice", password="Qu1et-River-88x")
        self.client.get(reverse("chat:conversation", args=[self.bob.pk]))
        message = Message.objects.get()
        self.assertTrue(message.is_read)

    def test_conversation_rejects_self(self):
        self.client.login(username="alice", password="Qu1et-River-88x")
        response = self.client.get(reverse("chat:conversation", args=[self.alice.pk]))
        self.assertEqual(response.status_code, 302)

    def test_conversation_reports_peer_online(self):
        add_connection(self.bob.pk)
        self.client.login(username="alice", password="Qu1et-River-88x")
        response = self.client.get(reverse("chat:conversation", args=[self.bob.pk]))
        self.assertEqual(response.context["other_online"], True)

    def test_messages_api_returns_thread_in_order(self):
        first = Message(
            sender=self.alice, receiver=self.bob, body="خرید اول"
        )
        second = Message(sender=self.bob, receiver=self.alice, body="سلام")
        Message.objects.bulk_create([first, second])
        Message.objects.filter(body="خرید اول").update(
            created_at=Message.objects.order_by("created_at")
            .first()
            .created_at
            - timedelta(seconds=5)
        )

        self.client.login(username="alice", password="Qu1et-River-88x")
        response = self.client.get(reverse("chat:messages_api", args=[self.bob.pk]))
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload["messages"]), 2)
        self.assertEqual(payload["messages"][0]["body"], "خرید اول")
        self.assertEqual(payload["messages"][1]["body"], "سلام")

    def test_messages_api_includes_attachment_fields(self):
        Message.objects.create(
            sender=self.alice,
            receiver=self.bob,
            file="chat/abc.png",
            file_name="abc.png",
        )
        self.client.login(username="alice", password="Qu1et-River-88x")
        response = self.client.get(reverse("chat:messages_api", args=[self.bob.pk]))
        item = response.json()["messages"][0]
        self.assertEqual(item["file"], "chat/abc.png")
        self.assertEqual(item["file_name"], "abc.png")
        self.assertFalse(item["is_voice"])

    def test_messages_api_includes_nested_reply(self):
        original = Message.objects.create(sender=self.bob, receiver=self.alice, body="اصلی")
        Message.objects.create(
            sender=self.alice, receiver=self.bob, body="پاسخ", reply_to=original
        )
        self.client.login(username="alice", password="Qu1et-River-88x")
        response = self.client.get(reverse("chat:messages_api", args=[self.bob.pk]))
        reply_item = response.json()["messages"][1]
        self.assertEqual(reply_item["body"], "پاسخ")
        reply = reply_item["reply"]
        self.assertEqual(
            set(reply),
            {"id", "sender_id", "sender_username", "body", "file_name", "is_voice"},
        )
        self.assertEqual(reply["id"], original.pk)
        self.assertEqual(reply["sender_id"], self.bob.pk)
        self.assertEqual(reply["sender_username"], "bob")
        self.assertEqual(reply["body"], "اصلی")

    def test_messages_api_truncates_long_reply_preview(self):
        long_body = "ب" * 300
        original = Message.objects.create(
            sender=self.bob, receiver=self.alice, body=long_body
        )
        Message.objects.create(
            sender=self.alice, receiver=self.bob, body="کوتاه", reply_to=original
        )
        self.client.login(username="alice", password="Qu1et-River-88x")
        response = self.client.get(reverse("chat:messages_api", args=[self.bob.pk]))
        reply = response.json()["messages"][1]["reply"]
        self.assertEqual(len(reply["body"]), 180)

    def test_messages_api_reply_is_null_without_reply_to(self):
        Message.objects.create(sender=self.bob, receiver=self.alice, body="ساده")
        self.client.login(username="alice", password="Qu1et-River-88x")
        response = self.client.get(reverse("chat:messages_api", args=[self.bob.pk]))
        self.assertIsNone(response.json()["messages"][0]["reply"])


class UploadTests(TestCase):
    def setUp(self):
        cache.clear()
        User = get_user_model()
        self.alice = User.objects.create_user("alice", password="Qu1et-River-88x")
        self.client.login(username="alice", password="Qu1et-River-88x")
        self.url = reverse("chat:upload_api")

    def tearDown(self):
        cache.clear()

    def test_upload_requires_login(self):
        self.client.logout()
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 302)

    def test_upload_requires_post(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 405)

    def test_upload_rejects_missing_file(self):
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 400)

    def test_upload_accepts_image(self):
        upload = SimpleUploadedFile("pic.png", b"\x89PNG\r\n\x1a\n", "image/png")
        response = self.client.post(self.url, {"file": upload})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["file"].startswith("chat/"))
        self.assertTrue(data["file"].endswith(".png"))
        self.assertEqual(data["file_name"], "pic.png")
        self.assertFalse(data["is_voice"])

    def test_upload_detects_voice(self):
        upload = SimpleUploadedFile("note.ogg", b"OggS", "audio/ogg")
        response = self.client.post(self.url, {"file": upload})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["is_voice"])

    def test_upload_rejects_disallowed_extension(self):
        upload = SimpleUploadedFile("run.exe", b"MZ", "application/octet-stream")
        response = self.client.post(self.url, {"file": upload})
        self.assertEqual(response.status_code, 400)

    def test_upload_rejects_disallowed_content_type(self):
        upload = SimpleUploadedFile("pic.png", b"x", "text/x-python")
        response = self.client.post(self.url, {"file": upload})
        self.assertEqual(response.status_code, 400)

    def test_upload_rejects_oversized_file(self):
        big = SimpleUploadedFile("big.png", b"a" * 4096, "image/png")
        from . import views as chat_views

        original = chat_views.MAX_UPLOAD_SIZE
        chat_views.MAX_UPLOAD_SIZE = 1024
        try:
            response = self.client.post(self.url, {"file": big})
        finally:
            chat_views.MAX_UPLOAD_SIZE = original
        self.assertEqual(response.status_code, 400)


class PresenceTests(TestCase):
    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def test_touch_marks_online(self):
        User = get_user_model()
        user = User.objects.create_user("alice", password="Qu1et-River-88x")
        self.assertFalse(is_online(user.pk))
        self.assertEqual(add_connection(user.pk), 1)
        self.assertTrue(is_online(user.pk))
        touch(user.pk)
        self.assertTrue(is_online(user.pk))

    def test_socket_counting_and_is_online(self):
        User = get_user_model()
        user = User.objects.create_user("bob", password="Qu1et-River-88x")
        self.assertFalse(is_online(user.pk))

        self.assertEqual(add_connection(user.pk), 1)
        self.assertTrue(is_online(user.pk))

        self.assertEqual(add_connection(user.pk), 2)
        self.assertTrue(is_online(user.pk))

        self.assertEqual(remove_connection(user.pk), 1)
        self.assertTrue(is_online(user.pk))

        self.assertEqual(remove_connection(user.pk), 0)
        self.assertFalse(is_online(user.pk))

        self.assertEqual(remove_connection(user.pk), -1)
        self.assertFalse(is_online(user.pk))

    def test_touch_is_noop_without_open_socket(self):
        User = get_user_model()
        user = User.objects.create_user("carol", password="Qu1et-River-88x")
        touch(user.pk)
        self.assertFalse(is_online(user.pk))


def _ws_app(user, other_id):
    async def app(scope, receive, send):
        scope = dict(scope)
        scope["user"] = user
        scope["url_route"] = {"kwargs": {"user_id": str(other_id)}}
        return await ChatConsumer.as_asgi()(scope, receive, send)

    return app


def _notify_app(user):
    async def app(scope, receive, send):
        scope = dict(scope)
        scope["user"] = user
        return await NotifyConsumer.as_asgi()(scope, receive, send)

    return app


def _run(coro):
    return asyncio.run(coro)


class ConsumerTests(TransactionTestCase):
    def setUp(self):
        cache.clear()
        User = get_user_model()
        self.alice = User.objects.create_user("alice", password="Qu1et-River-88x")
        self.bob = User.objects.create_user("bob", password="Qu1et-River-88x")

    def tearDown(self):
        cache.clear()

    def _communicator(self, user, other_id):
        return WebsocketCommunicator(_ws_app(user, other_id), f"/ws/chat/{other_id}/")

    def test_anonymous_is_rejected(self):
        async def scenario():
            comm = self._communicator(AnonymousUser(), self.bob.pk)
            connected, _ = await comm.connect()
            self.assertFalse(connected)
            await comm.disconnect()

        _run(scenario())

    def test_peer_presence_reflects_real_connection(self):

        async def scenario():
            alice_sock = self._communicator(self.alice, self.bob.pk)
            connected, _ = await alice_sock.connect()
            self.assertTrue(connected)
            first = await alice_sock.receive_json_from()
            self.assertEqual(first["type"], "presence")
            self.assertFalse(first["online"])

            bob_sock = self._communicator(self.bob, self.alice.pk)
            connected, _ = await bob_sock.connect()
            self.assertTrue(connected)
            await bob_sock.receive_json_from()

            update = await alice_sock.receive_json_from()
            self.assertEqual(update["type"], "presence")
            self.assertTrue(update["online"])

            await bob_sock.disconnect()
            offline = await alice_sock.receive_json_from()
            self.assertEqual(offline["type"], "presence")
            self.assertFalse(offline["online"])

            await alice_sock.disconnect()

        _run(scenario())

    def test_file_message_is_persisted_and_broadcast(self):

        async def scenario():
            stored = default_storage.save("chat/demo.png", ContentFile(b"png-bytes"))

            alice_sock = self._communicator(self.alice, self.bob.pk)
            await alice_sock.connect()
            await alice_sock.receive_json_from()

            bob_sock = self._communicator(self.bob, self.alice.pk)
            await bob_sock.connect()
            await bob_sock.receive_json_from()
            await alice_sock.receive_json_from()

            await alice_sock.send_json_to(
                {
                    "file": stored,
                    "file_name": "demo.png",
                    "is_voice": False,
                }
            )

            received = await bob_sock.receive_json_from()
            self.assertEqual(received["type"], "chat.message")
            self.assertEqual(received["file"], stored)
            self.assertEqual(received["file_name"], "demo.png")
            self.assertFalse(received["is_voice"])

            await alice_sock.disconnect()
            await bob_sock.disconnect()

        _run(scenario())
        message = Message.objects.get()
        self.assertTrue(message.file.name.startswith("chat/"))
        self.assertTrue(message.file.name.endswith(".png"))
        self.assertEqual(message.file_name, "demo.png")
        self.assertFalse(message.is_voice)

    def test_unknown_file_path_is_rejected(self):

        async def scenario():
            alice_sock = self._communicator(self.alice, self.bob.pk)
            await alice_sock.connect()
            await alice_sock.receive_json_from()

            await alice_sock.send_json_to({"file": "chat/does-not-exist.png"})
            err = await alice_sock.receive_json_from()
            self.assertEqual(err["type"], "error")
            await alice_sock.disconnect()

        _run(scenario())
        self.assertFalse(Message.objects.exists())

    def test_reply_to_is_persisted_and_broadcast(self):
        original = Message.objects.create(sender=self.bob, receiver=self.alice, body="اصلی")

        async def scenario():
            alice_sock = self._communicator(self.alice, self.bob.pk)
            await alice_sock.connect()
            await alice_sock.receive_json_from()

            bob_sock = self._communicator(self.bob, self.alice.pk)
            await bob_sock.connect()
            await bob_sock.receive_json_from()
            await alice_sock.receive_json_from()

            await alice_sock.send_json_to(
                {"body": "پاسخ", "reply_to": original.pk}
            )

            received = await bob_sock.receive_json_from()
            self.assertEqual(received["type"], "chat.message")
            self.assertEqual(received["body"], "پاسخ")
            self.assertEqual(received["reply"]["id"], original.pk)
            self.assertEqual(received["reply"]["sender_username"], "bob")
            self.assertEqual(received["reply"]["body"], "اصلی")

            await alice_sock.disconnect()
            await bob_sock.disconnect()

        _run(scenario())
        message = Message.objects.exclude(pk=original.pk).get()
        self.assertEqual(message.reply_to_id, original.pk)

    def test_foreign_reply_to_id_is_ignored(self):
        carol = get_user_model().objects.create_user(
            "carol", password="Qu1et-River-88x"
        )
        foreign = Message.objects.create(sender=self.bob, receiver=carol, body="بیگانه")

        async def scenario():
            alice_sock = self._communicator(self.alice, self.bob.pk)
            await alice_sock.connect()
            await alice_sock.receive_json_from()

            bob_sock = self._communicator(self.bob, self.alice.pk)
            await bob_sock.connect()
            await bob_sock.receive_json_from()
            await alice_sock.receive_json_from()

            await alice_sock.send_json_to(
                {"body": "کج رفت", "reply_to": foreign.pk}
            )

            received = await bob_sock.receive_json_from()
            self.assertEqual(received["type"], "chat.message")
            self.assertIsNone(received["reply"])

            await alice_sock.disconnect()
            await bob_sock.disconnect()

        _run(scenario())
        message = Message.objects.get(body="کج رفت")
        self.assertIsNone(message.reply_to_id)


class UnreadCountTests(TestCase):
    def setUp(self):
        cache.clear()
        User = get_user_model()
        self.alice = User.objects.create_user("alice", password="Qu1et-River-88x")
        self.bob = User.objects.create_user("bob", password="Qu1et-River-88x")
        self.carol = User.objects.create_user("carol", password="Qu1et-River-88x")

    def tearDown(self):
        cache.clear()

    def test_counts_distinct_conversations(self):
        Message.objects.create(sender=self.bob, receiver=self.alice, body="یک")
        Message.objects.create(sender=self.bob, receiver=self.alice, body="دو")
        Message.objects.create(sender=self.carol, receiver=self.alice, body="سه")
        self.assertEqual(unread_chat_count(self.alice), 2)

    def test_read_and_hidden_messages_do_not_count(self):
        Message.objects.create(
            sender=self.bob, receiver=self.alice, body="خوانده‌شده", is_read=True
        )
        hidden = Message.objects.create(
            sender=self.carol, receiver=self.alice, body="حذف‌شده"
        )
        MessageDeletion.objects.create(message=hidden, user=self.alice)
        self.assertEqual(unread_chat_count(self.alice), 0)

    def test_header_badge_is_shown_when_unread_exists(self):
        Message.objects.create(sender=self.bob, receiver=self.alice, body="سلام")
        self.client.login(username="alice", password="Qu1et-River-88x")
        content = self.client.get(reverse("chat:inbox")).content.decode()
        self.assertIn("data-unread-chats", content)
        self.assertNotIn("data-unread-chats hidden", content)

    def test_header_badge_is_hidden_without_unread(self):
        self.client.login(username="alice", password="Qu1et-River-88x")
        content = self.client.get(reverse("chat:inbox")).content.decode()
        self.assertIn("data-unread-chats hidden", content)


class MuteApiTests(TestCase):
    def setUp(self):
        cache.clear()
        User = get_user_model()
        self.alice = User.objects.create_user("alice", password="Qu1et-River-88x")
        self.bob = User.objects.create_user("bob", password="Qu1et-River-88x")
        self.url = reverse("chat:mute", args=[self.bob.pk])

    def tearDown(self):
        cache.clear()

    def test_requires_login(self):
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 302)

    def test_rejects_get(self):
        self.client.login(username="alice", password="Qu1et-River-88x")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 405)

    def test_rejects_self(self):
        self.client.login(username="alice", password="Qu1et-River-88x")
        response = self.client.post(reverse("chat:mute", args=[self.alice.pk]))
        self.assertEqual(response.status_code, 400)

    def test_toggles_mute_state(self):
        self.client.login(username="alice", password="Qu1et-River-88x")

        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["muted"])
        self.assertTrue(Mute.objects.filter(owner=self.alice, peer=self.bob).exists())

        response = self.client.post(self.url)
        self.assertFalse(response.json()["muted"])
        self.assertFalse(Mute.objects.filter(owner=self.alice, peer=self.bob).exists())


class MessagesApiExtraTests(TestCase):
    def setUp(self):
        cache.clear()
        User = get_user_model()
        self.alice = User.objects.create_user("alice", password="Qu1et-River-88x")
        self.bob = User.objects.create_user("bob", password="Qu1et-River-88x")
        self.url = reverse("chat:messages_api", args=[self.bob.pk])

    def tearDown(self):
        cache.clear()

    def test_returns_read_flag(self):
        outgoing = Message.objects.create(sender=self.alice, receiver=self.bob, body="من")
        Message.objects.create(sender=self.bob, receiver=self.alice, body="او")
        self.client.login(username="alice", password="Qu1et-River-88x")

        payload = self.client.get(self.url).json()["messages"]
        by_body = {item["body"]: item for item in payload}
        self.assertFalse(by_body["من"]["is_read"])
        self.assertTrue(by_body["او"]["is_read"])

    def test_excludes_messages_deleted_for_me(self):
        Message.objects.create(sender=self.bob, receiver=self.alice, body="پنهان")
        hidden = Message.objects.create(sender=self.alice, receiver=self.bob, body="من")
        MessageDeletion.objects.create(message=hidden, user=self.alice)
        self.client.login(username="alice", password="Qu1et-River-88x")

        payload = self.client.get(self.url).json()["messages"]
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]["body"], "پنهان")


class NotifyConsumerTests(TransactionTestCase):
    def setUp(self):
        cache.clear()
        User = get_user_model()
        self.alice = User.objects.create_user("alice", password="Qu1et-River-88x")
        self.bob = User.objects.create_user("bob", password="Qu1et-River-88x")

    def tearDown(self):
        cache.clear()

    def test_anonymous_is_rejected(self):
        async def scenario():
            comm = WebsocketCommunicator(_notify_app(AnonymousUser()), "/ws/notify/")
            connected, _ = await comm.connect()
            self.assertFalse(connected)
            await comm.disconnect()

        _run(scenario())

    def test_sync_carries_unread_count(self):
        Message.objects.create(sender=self.bob, receiver=self.alice, body="سلام")

        async def scenario():
            comm = WebsocketCommunicator(_notify_app(self.alice), "/ws/notify/")
            connected, _ = await comm.connect()
            self.assertTrue(connected)
            data = await comm.receive_json_from()
            self.assertEqual(data["type"], "notify.sync")
            self.assertEqual(data["unread_chats"], 1)
            await comm.disconnect()

        _run(scenario())


class ReadAndDeleteTests(TransactionTestCase):
    def setUp(self):
        cache.clear()
        User = get_user_model()
        self.alice = User.objects.create_user("alice", password="Qu1et-River-88x")
        self.bob = User.objects.create_user("bob", password="Qu1et-River-88x")

    def tearDown(self):
        cache.clear()

    def _communicator(self, user, other_id):
        return WebsocketCommunicator(_ws_app(user, other_id), f"/ws/chat/{other_id}/")

    async def _connected_pair(self):
        alice_sock = self._communicator(self.alice, self.bob.pk)
        connected, _ = await alice_sock.connect()
        self.assertTrue(connected)
        await alice_sock.receive_json_from()

        bob_sock = self._communicator(self.bob, self.alice.pk)
        connected, _ = await bob_sock.connect()
        self.assertTrue(connected)
        await bob_sock.receive_json_from()
        await alice_sock.receive_json_from()
        return alice_sock, bob_sock

    def test_read_receipt_notifies_the_sender(self):
        message = Message.objects.create(sender=self.alice, receiver=self.bob, body="سلام")

        async def scenario():
            alice_sock, bob_sock = await self._connected_pair()

            await bob_sock.send_json_to({"type": "read"})
            echo = await bob_sock.receive_json_from()
            self.assertEqual(echo["type"], "chat.read")
            update = await alice_sock.receive_json_from()

            self.assertEqual(update["type"], "chat.read")
            self.assertEqual(update["message_ids"], [message.pk])
            self.assertEqual(update["reader_id"], self.bob.pk)

            await alice_sock.disconnect()
            await bob_sock.disconnect()

        _run(scenario())
        self.assertTrue(Message.objects.get(pk=message.pk).is_read)

    def test_delete_message_for_everyone(self):
        message = Message.objects.create(sender=self.alice, receiver=self.bob, body="پیام")

        async def scenario():
            alice_sock, bob_sock = await self._connected_pair()

            await alice_sock.send_json_to(
                {"type": "delete_message", "id": message.pk, "for_everyone": True}
            )

            for sock in (alice_sock, bob_sock):
                event = await sock.receive_json_from()
                self.assertEqual(event["type"], "chat.message.deleted")
                self.assertTrue(event["for_everyone"])
                self.assertEqual(event["id"], message.pk)

            await alice_sock.disconnect()
            await bob_sock.disconnect()

        _run(scenario())
        self.assertFalse(Message.objects.exists())

    def test_hard_delete_nulls_reply_fk(self):
        original = Message.objects.create(sender=self.alice, receiver=self.bob, body="اصلی")
        reply = Message.objects.create(
            sender=self.bob, receiver=self.alice, body="پاسخ", reply_to=original
        )

        async def scenario():
            alice_sock, bob_sock = await self._connected_pair()

            await alice_sock.send_json_to(
                {"type": "delete_message", "id": original.pk, "for_everyone": True}
            )

            for sock in (alice_sock, bob_sock):
                event = await sock.receive_json_from()
                self.assertEqual(event["type"], "chat.message.deleted")

            await alice_sock.disconnect()
            await bob_sock.disconnect()

        _run(scenario())
        reply.refresh_from_db()
        self.assertIsNone(reply.reply_to_id)
        self.assertTrue(Message.objects.filter(pk=reply.pk).exists())

    def test_delete_message_for_me_only(self):
        message = Message.objects.create(sender=self.alice, receiver=self.bob, body="پیام")

        async def scenario():
            alice_sock, bob_sock = await self._connected_pair()

            await bob_sock.send_json_to(
                {"type": "delete_message", "id": message.pk, "for_everyone": False}
            )

            for sock in (alice_sock, bob_sock):
                event = await sock.receive_json_from()
                self.assertEqual(event["type"], "chat.message.deleted")
                self.assertFalse(event["for_everyone"])
                self.assertEqual(event["target_user_id"], self.bob.pk)

            await alice_sock.disconnect()
            await bob_sock.disconnect()

        _run(scenario())
        self.assertTrue(Message.objects.filter(pk=message.pk).exists())
        self.assertTrue(
            MessageDeletion.objects.filter(message=message, user=self.bob).exists()
        )

    def test_cannot_delete_someone_elses_message_for_everyone(self):
        message = Message.objects.create(sender=self.alice, receiver=self.bob, body="پیام")

        async def scenario():
            alice_sock, bob_sock = await self._connected_pair()

            await bob_sock.send_json_to(
                {"type": "delete_message", "id": message.pk, "for_everyone": True}
            )

            event = await bob_sock.receive_json_from()
            self.assertFalse(event["for_everyone"])

            await alice_sock.disconnect()
            await bob_sock.disconnect()

        _run(scenario())
        self.assertTrue(Message.objects.filter(pk=message.pk).exists())

    def test_delete_conversation_clears_thread_for_both(self):
        Message.objects.create(sender=self.alice, receiver=self.bob, body="یک")
        Message.objects.create(sender=self.bob, receiver=self.alice, body="دو")

        async def scenario():
            alice_sock, bob_sock = await self._connected_pair()

            await alice_sock.send_json_to({"type": "delete_conversation"})

            for sock in (alice_sock, bob_sock):
                event = await sock.receive_json_from()
                self.assertEqual(event["type"], "chat.conversation.deleted")

            await alice_sock.disconnect()
            await bob_sock.disconnect()

        _run(scenario())
        self.assertFalse(Message.objects.exists())


def make_group(owner, *others, name="گروه آزمایشی"):
    group = ChatGroup.objects.create(name=name, created_by=owner)
    GroupMembership.objects.create(group=group, user=owner, is_admin=True)
    for user in others:
        GroupMembership.objects.create(group=group, user=user)
    return group


class TextUploadTests(TestCase):
    def setUp(self):
        cache.clear()
        User = get_user_model()
        self.alice = User.objects.create_user("alice", password="Qu1et-River-88x")
        self.client.login(username="alice", password="Qu1et-River-88x")
        self.url = reverse("chat:upload_api")

    def tearDown(self):
        cache.clear()

    def test_upload_accepts_txt_plain(self):
        upload = SimpleUploadedFile("notes.txt", b"hello", "text/plain")
        response = self.client.post(self.url, {"file": upload})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["file"].endswith(".txt"))
        self.assertEqual(data["file_name"], "notes.txt")
        self.assertFalse(data["is_voice"])

    def test_upload_accepts_txt_with_generic_content_type(self):
        upload = SimpleUploadedFile("notes.txt", b"hello", "application/octet-stream")
        response = self.client.post(self.url, {"file": upload})
        self.assertEqual(response.status_code, 200)

    def test_upload_accepts_docx(self):
        upload = SimpleUploadedFile(
            "report.docx",
            b"PK",
            "application/vnd.openxmlformats-officedocument"
            ".wordprocessingml.document",
        )
        response = self.client.post(self.url, {"file": upload})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["file"].endswith(".docx"))

    def test_upload_rejects_html(self):
        upload = SimpleUploadedFile("page.html", b"<b>x</b>", "text/html")
        response = self.client.post(self.url, {"file": upload})
        self.assertEqual(response.status_code, 400)

    def test_upload_still_rejects_exe(self):
        upload = SimpleUploadedFile("run.exe", b"MZ", "application/octet-stream")
        response = self.client.post(self.url, {"file": upload})
        self.assertEqual(response.status_code, 400)


class GroupViewTests(TestCase):
    def setUp(self):
        cache.clear()
        User = get_user_model()
        self.alice = User.objects.create_user("alice", password="Qu1et-River-88x")
        self.bob = User.objects.create_user("bob", password="Qu1et-River-88x")
        self.carol = User.objects.create_user("carol", password="Qu1et-River-88x")
        self.client.login(username="alice", password="Qu1et-River-88x")

    def tearDown(self):
        cache.clear()

    def _login_as(self, user):
        self.client.logout()
        self.client.login(username=user.username, password="Qu1et-River-88x")

    def test_group_create_marks_creator_admin(self):
        response = self.client.post(
            reverse("chat:group_create"),
            {"name": "خانواده", "members": [str(self.bob.pk)]},
        )
        self.assertEqual(response.status_code, 302)
        group = ChatGroup.objects.get(name="خانواده")
        self.assertEqual(
            response.url, reverse("chat:group_conversation", args=[group.pk])
        )
        self.assertTrue(
            GroupMembership.objects.get(group=group, user=self.alice).is_admin
        )
        self.assertFalse(
            GroupMembership.objects.get(group=group, user=self.bob).is_admin
        )

    def test_group_create_requires_a_member(self):
        response = self.client.post(reverse("chat:group_create"), {"name": "تنها"})
        self.assertEqual(response.status_code, 302)
        self.assertIn("error", response.url)
        self.assertFalse(ChatGroup.objects.exists())

    def test_inbox_lists_my_groups_and_hides_others(self):
        mine = make_group(self.alice, self.bob, name="گروه من")
        make_group(self.bob, self.carol, name="گروه بیگانه")

        response = self.client.get(reverse("chat:inbox"))

        self.assertContains(response, "گروه من")
        self.assertContains(
            response, reverse("chat:group_conversation", args=[mine.pk])
        )
        self.assertNotContains(response, "گروه بیگانه")

    def test_group_page_404_for_non_member(self):
        group = make_group(self.bob, self.carol, name="بدون من")
        response = self.client.get(
            reverse("chat:group_conversation", args=[group.pk])
        )
        self.assertEqual(response.status_code, 404)

    def test_group_messages_api_404_for_non_member(self):
        group = make_group(self.bob, self.carol, name="بیگانه")
        response = self.client.get(
            reverse("chat:group_messages_api", args=[group.pk])
        )
        self.assertEqual(response.status_code, 404)

    def test_last_admin_cannot_leave(self):
        group = make_group(self.alice, self.bob, name="ترک ناممکن")
        response = self.client.post(reverse("chat:group_leave", args=[group.pk]))
        self.assertEqual(response.status_code, 400)
        self.assertTrue(
            GroupMembership.objects.filter(group=group, user=self.alice).exists()
        )

    def test_non_admin_member_can_leave(self):
        group = make_group(self.alice, self.bob, name="خروج آزاد")
        self._login_as(self.bob)
        response = self.client.post(reverse("chat:group_leave", args=[group.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            GroupMembership.objects.filter(group=group, user=self.bob).exists()
        )

    def test_admin_can_remove_member(self):
        group = make_group(self.alice, self.bob, name="حذف عضو")
        response = self.client.post(
            reverse("chat:group_members", args=[group.pk]),
            {"action": "remove", "user_id": str(self.bob.pk)},
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            GroupMembership.objects.filter(group=group, user=self.bob).exists()
        )

    def test_non_admin_cannot_remove_member(self):
        group = make_group(self.alice, self.bob, name="فقط مدیر")
        self._login_as(self.bob)
        response = self.client.post(
            reverse("chat:group_members", args=[group.pk]),
            {"action": "remove", "user_id": str(self.alice.pk)},
        )
        self.assertEqual(response.status_code, 403)
        self.assertTrue(
            GroupMembership.objects.filter(group=group, user=self.alice).exists()
        )

    def test_group_mute_toggle(self):
        group = make_group(self.alice, self.bob, name="گروه بی‌صدا")
        url = reverse("chat:group_mute", args=[group.pk])

        self.assertTrue(self.client.post(url).json()["muted"])
        self.assertTrue(
            GroupMute.objects.filter(owner=self.alice, group=group).exists()
        )

        self.assertFalse(self.client.post(url).json()["muted"])
        self.assertFalse(
            GroupMute.objects.filter(owner=self.alice, group=group).exists()
        )

    def test_group_delete_cascades_messages(self):
        group = make_group(self.alice, self.bob, name="حذف گروه")
        Message.objects.create(sender=self.alice, group=group, body="سلام")

        response = self.client.post(reverse("chat:group_delete", args=[group.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertFalse(ChatGroup.objects.filter(pk=group.pk).exists())
        self.assertFalse(Message.objects.exists())

    def test_non_admin_cannot_delete_group(self):
        group = make_group(self.alice, self.bob, name="حذف ممنوع")
        self._login_as(self.bob)
        response = self.client.post(reverse("chat:group_delete", args=[group.pk]))
        self.assertEqual(response.status_code, 403)
        self.assertTrue(ChatGroup.objects.filter(pk=group.pk).exists())

    def test_group_messages_api_marks_seen(self):
        group = make_group(self.alice, self.bob, name="خوانده‌شده")
        Message.objects.create(sender=self.bob, group=group, body="هی")

        response = self.client.get(
            reverse("chat:group_messages_api", args=[group.pk])
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload["messages"]), 1)
        self.assertEqual(payload["messages"][0]["body"], "هی")
        membership = GroupMembership.objects.get(group=group, user=self.alice)
        self.assertIsNotNone(membership.last_seen_at)
        self.assertEqual(unread_chat_count(self.alice), 0)

    def test_group_messages_api_includes_nested_reply(self):
        group = make_group(self.alice, self.bob, name="ریپلای")
        original = Message.objects.create(sender=self.bob, group=group, body="اصلی")
        Message.objects.create(
            sender=self.alice, group=group, body="پاسخ", reply_to=original
        )

        response = self.client.get(
            reverse("chat:group_messages_api", args=[group.pk])
        )

        reply_item = response.json()["messages"][1]
        self.assertEqual(reply_item["group_id"], group.pk)
        reply = reply_item["reply"]
        self.assertEqual(reply["id"], original.pk)
        self.assertEqual(reply["sender_username"], "bob")
        self.assertEqual(reply["body"], "اصلی")


class GroupUnreadTests(TestCase):
    def setUp(self):
        cache.clear()
        User = get_user_model()
        self.alice = User.objects.create_user("alice", password="Qu1et-River-88x")
        self.bob = User.objects.create_user("bob", password="Qu1et-River-88x")
        self.group = make_group(self.alice, self.bob, name="شمارش")

    def tearDown(self):
        cache.clear()

    def test_counts_group_messages_from_others_only(self):
        self.assertEqual(unread_chat_count(self.alice), 0)

        Message.objects.create(sender=self.bob, group=self.group, body="هی")

        self.assertEqual(unread_chat_count(self.alice), 1)
        self.assertEqual(unread_chat_count(self.bob), 0)

    def test_seen_group_messages_do_not_count(self):
        message = Message.objects.create(sender=self.bob, group=self.group, body="هی")
        GroupMembership.objects.filter(user=self.alice, group=self.group).update(
            last_seen_at=message.created_at
        )
        self.assertEqual(unread_chat_count(self.alice), 0)

    def test_hidden_group_messages_do_not_count(self):
        message = Message.objects.create(sender=self.bob, group=self.group, body="هی")
        MessageDeletion.objects.create(message=message, user=self.alice)
        self.assertEqual(unread_chat_count(self.alice), 0)

    def test_direct_and_group_counts_add_up(self):
        Message.objects.create(sender=self.bob, receiver=self.alice, body="سلام")
        self.assertEqual(unread_chat_count(self.alice), 1)

        Message.objects.create(sender=self.bob, group=self.group, body="گروهی")
        self.assertEqual(unread_chat_count(self.alice), 2)


class ConversationDeleteApiTests(TestCase):
    def setUp(self):
        cache.clear()
        User = get_user_model()
        self.alice = User.objects.create_user("alice", password="Qu1et-River-88x")
        self.bob = User.objects.create_user("bob", password="Qu1et-River-88x")
        self.url = reverse("chat:conversation_delete", args=[self.bob.pk])

    def tearDown(self):
        cache.clear()

    def test_requires_login(self):
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 302)

    def test_rejects_get(self):
        self.client.login(username="alice", password="Qu1et-River-88x")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 405)

    def test_clears_thread_for_both(self):
        Message.objects.create(sender=self.alice, receiver=self.bob, body="یک")
        Message.objects.create(sender=self.bob, receiver=self.alice, body="دو")
        self.client.login(username="alice", password="Qu1et-River-88x")

        response = self.client.post(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["deleted"], 2)
        self.assertFalse(Message.objects.exists())


def _group_ws_app(user, group_id):
    async def app(scope, receive, send):
        scope = dict(scope)
        scope["user"] = user
        scope["url_route"] = {"kwargs": {"group_id": str(group_id)}}
        return await GroupConsumer.as_asgi()(scope, receive, send)

    return app


class GroupConsumerTests(TransactionTestCase):
    def setUp(self):
        cache.clear()
        User = get_user_model()
        self.alice = User.objects.create_user("alice", password="Qu1et-River-88x")
        self.bob = User.objects.create_user("bob", password="Qu1et-River-88x")
        self.carol = User.objects.create_user("carol", password="Qu1et-River-88x")
        self.group = make_group(self.alice, self.bob, name="زنده")

    def tearDown(self):
        cache.clear()

    def _communicator(self, user, group_id=None):
        group_id = self.group.pk if group_id is None else group_id
        return WebsocketCommunicator(
            _group_ws_app(user, group_id), f"/ws/chat/group/{group_id}/"
        )

    def test_anonymous_is_rejected(self):
        async def scenario():
            comm = self._communicator(AnonymousUser())
            connected, _ = await comm.connect()
            self.assertFalse(connected)
            await comm.disconnect()

        asyncio.run(scenario())

    def test_non_member_is_rejected(self):
        async def scenario():
            comm = self._communicator(self.carol)
            connected, _ = await comm.connect()
            self.assertFalse(connected)
            await comm.disconnect()

        asyncio.run(scenario())

    def test_message_broadcasts_to_every_member(self):
        async def scenario():
            alice_sock = self._communicator(self.alice)
            connected, _ = await alice_sock.connect()
            self.assertTrue(connected)

            bob_sock = self._communicator(self.bob)
            connected, _ = await bob_sock.connect()
            self.assertTrue(connected)

            await alice_sock.send_json_to({"body": "سلام گروه"})

            received = await bob_sock.receive_json_from()
            self.assertEqual(received["type"], "chat.message")
            self.assertEqual(received["body"], "سلام گروه")
            self.assertEqual(received["group_id"], self.group.pk)

            own = await alice_sock.receive_json_from()
            self.assertEqual(own["type"], "chat.message")
            self.assertEqual(own["body"], "سلام گروه")

            await alice_sock.disconnect()
            await bob_sock.disconnect()

        asyncio.run(scenario())

        message = Message.objects.get()
        self.assertIsNone(message.receiver_id)
        self.assertEqual(message.group_id, self.group.pk)

    def test_group_reply_persists(self):
        original = Message.objects.create(sender=self.bob, group=self.group, body="اصلی")

        async def scenario():
            alice_sock = self._communicator(self.alice)
            connected, _ = await alice_sock.connect()
            self.assertTrue(connected)

            bob_sock = self._communicator(self.bob)
            connected, _ = await bob_sock.connect()
            self.assertTrue(connected)

            await alice_sock.send_json_to({"body": "پاسخ", "reply_to": original.pk})

            received = await bob_sock.receive_json_from()
            self.assertEqual(received["type"], "chat.message")
            self.assertEqual(received["reply"]["id"], original.pk)
            self.assertEqual(received["reply"]["sender_username"], "bob")

            await alice_sock.disconnect()
            await bob_sock.disconnect()

        asyncio.run(scenario())
        message = Message.objects.exclude(pk=original.pk).get()
        self.assertEqual(message.reply_to_id, original.pk)

    def test_group_foreign_reply_to_is_ignored(self):
        other_group = make_group(self.alice, self.carol, name="گروه دیگر")
        foreign = Message.objects.create(
            sender=self.alice, group=other_group, body="بیگانه"
        )

        async def scenario():
            alice_sock = self._communicator(self.alice)
            connected, _ = await alice_sock.connect()
            self.assertTrue(connected)

            bob_sock = self._communicator(self.bob)
            connected, _ = await bob_sock.connect()
            self.assertTrue(connected)

            await alice_sock.send_json_to(
                {"body": "کج رفت", "reply_to": foreign.pk}
            )

            received = await bob_sock.receive_json_from()
            self.assertEqual(received["type"], "chat.message")
            self.assertIsNone(received["reply"])

            await alice_sock.disconnect()
            await bob_sock.disconnect()

        asyncio.run(scenario())
        message = Message.objects.get(body="کج رفت")
        self.assertIsNone(message.reply_to_id)

    def test_unknown_file_path_is_rejected(self):
        async def scenario():
            comm = self._communicator(self.alice)
            connected, _ = await comm.connect()
            self.assertTrue(connected)

            await comm.send_json_to({"file": "chat/does-not-exist.png"})
            err = await comm.receive_json_from()
            self.assertEqual(err["type"], "error")
            await comm.disconnect()

        asyncio.run(scenario())
        self.assertFalse(Message.objects.exists())

    def test_clear_for_me_keeps_the_messages(self):
        Message.objects.create(sender=self.bob, group=self.group, body="برای همه")
        Message.objects.create(sender=self.alice, group=self.group, body="من")

        async def scenario():
            comm = self._communicator(self.alice)
            connected, _ = await comm.connect()
            self.assertTrue(connected)

            await comm.send_json_to({"type": "delete_conversation"})
            reply = await comm.receive_json_from()
            self.assertEqual(reply["type"], "chat.cleared_for_me")
            await comm.disconnect()

        asyncio.run(scenario())

        self.assertEqual(Message.objects.count(), 2)
        self.assertEqual(MessageDeletion.objects.filter(user=self.alice).count(), 2)
        self.assertEqual(unread_chat_count(self.alice), 0)
        # پاک کردن برای من نباید شمارش طرف مقابل را عوض کند.
        self.assertEqual(unread_chat_count(self.bob), 1)


class CleanupChatCommandTests(TestCase):
    def setUp(self):
        import tempfile

        from django.test import override_settings

        self.media = tempfile.mkdtemp()
        self.override = override_settings(MEDIA_ROOT=self.media)
        self.override.enable()
        User = get_user_model()
        self.alice = User.objects.create_user(username="alice", password="Qu1et-River-88x")
        self.bob = User.objects.create_user(username="bob", password="Qu1et-River-88x")

    def tearDown(self):
        import shutil

        self.override.disable()
        shutil.rmtree(self.media, ignore_errors=True)

    def _message(self, body="", with_file=False, days_old=0):
        message = Message.objects.create(sender=self.alice, receiver=self.bob, body=body)
        if with_file:
            message.file.save("pic.jpg", ContentFile(b"x" * 100), save=True)
        if days_old:
            Message.objects.filter(pk=message.pk).update(
                created_at=message.created_at - timedelta(days=days_old)
            )
        return message

    def _run(self, *args):
        from io import StringIO

        from django.core.management import call_command

        call_command("cleanup_chat", *args, stdout=StringIO())

    def test_delete_all_messages_removes_their_files(self):
        message = self._message("hi", with_file=True)
        path = message.file.path
        self._run("--messages")
        self.assertFalse(Message.objects.exists())
        self.assertFalse(default_storage.exists(path))

    def test_delete_messages_older_than_keeps_recent(self):
        self._message("old", days_old=40)
        recent = self._message("new")
        self._run("--messages", "--older-than", "30")
        self.assertEqual(list(Message.objects.all()), [recent])

    def test_delete_media_keeps_text_and_drops_file_only_messages(self):
        with_text = self._message("caption", with_file=True)
        self._message("", with_file=True)
        text_only = self._message("plain")
        self._run("--media")

        self.assertEqual(set(Message.objects.all()), {with_text, text_only})
        with_text.refresh_from_db()
        self.assertFalse(with_text.file)
        self.assertEqual(list(Path(self.media).rglob("*.*")), [])

    def test_requires_an_action(self):
        from django.core.management.base import CommandError

        with self.assertRaises(CommandError):
            self._run()
