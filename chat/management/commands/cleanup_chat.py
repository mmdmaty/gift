import os
import time
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from chat.models import Message

CHAT_MEDIA_DIR = "chat"


class Command(BaseCommand):
    help = "Free disk space by deleting chat messages and/or chat media files."

    def add_arguments(self, parser):
        parser.add_argument(
            "--messages",
            action="store_true",
            help="Delete chat messages (and the files attached to them).",
        )
        parser.add_argument(
            "--media",
            action="store_true",
            help="Delete chat media files; text messages are kept.",
        )
        parser.add_argument(
            "--older-than",
            type=int,
            default=0,
            metavar="DAYS",
            help="Only delete items older than DAYS days (0 = everything).",
        )

    def handle(self, *args, **options):
        if not options["messages"] and not options["media"]:
            raise CommandError("Pass --messages and/or --media.")
        if options["older_than"] < 0:
            raise CommandError("--older-than must be 0 or more.")

        days = options["older_than"]
        cutoff = timezone.now() - timedelta(days=days) if days else None

        if options["messages"]:
            self._delete_messages(cutoff)
        if options["media"]:
            self._delete_media(cutoff)

    def _delete_messages(self, cutoff):
        messages = Message.objects.all()
        if cutoff:
            messages = messages.filter(created_at__lt=cutoff)

        files = [m.file for m in messages.exclude(file="").exclude(file__isnull=True).only("file")]
        with transaction.atomic():
            count, _ = messages.delete()
        for file in files:
            file.storage.delete(file.name)

        self.stdout.write(self.style.SUCCESS(f"Deleted {count} chat rows and {len(files)} attached files."))

    def _delete_media(self, cutoff):
        media_dir = Path(settings.MEDIA_ROOT) / CHAT_MEDIA_DIR
        cutoff_ts = cutoff.timestamp() if cutoff else time.time() + 1
        freed = removed = 0

        # walk the folder rather than the DB so orphaned uploads are cleaned too
        if media_dir.is_dir():
            for path in media_dir.rglob("*"):
                if path.is_file() and path.stat().st_mtime < cutoff_ts:
                    freed += path.stat().st_size
                    path.unlink()
                    removed += 1
            for folder in sorted(media_dir.rglob("*"), reverse=True):
                if folder.is_dir() and not any(folder.iterdir()):
                    folder.rmdir()

        # drop references to files that no longer exist; file-only messages become empty, so remove them
        dangling = [
            m for m in Message.objects.exclude(file="").exclude(file__isnull=True).only("id", "file", "body")
            if not os.path.exists(Path(settings.MEDIA_ROOT) / m.file.name)
        ]
        empty_ids = [m.id for m in dangling if not m.body.strip()]
        kept_ids = [m.id for m in dangling if m.body.strip()]
        with transaction.atomic():
            Message.objects.filter(id__in=empty_ids).delete()
            Message.objects.filter(id__in=kept_ids).update(file=None, file_name="", is_voice=False)

        self.stdout.write(self.style.SUCCESS(
            f"Deleted {removed} chat media files ({freed / 1024 / 1024:.1f} MB freed); "
            f"removed {len(empty_ids)} file-only messages, detached files from {len(kept_ids)} messages."
        ))
