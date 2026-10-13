REPLY_PREVIEW_LENGTH = 180


def reply_preview(message):
    if message is None:
        return None
    return {
        "id": message.id,
        "sender_id": message.sender_id,
        "sender_username": message.sender.get_username(),
        "body": (message.body or "").strip()[:REPLY_PREVIEW_LENGTH],
        "file_name": message.file_name,
        "is_voice": message.is_voice,
    }


def message_payload(message, *, group_id=None):
    payload = {
        "id": message.id,
        "body": message.body,
        "sender_id": message.sender_id,
        "sender_username": message.sender.get_username(),
        "created_at": message.created_at.isoformat(),
        "file": message.file.name if message.file else "",
        "file_name": message.file_name,
        "is_voice": message.is_voice,
        "is_read": message.is_read,
        "reply": reply_preview(message.reply_to) if message.reply_to_id else None,
    }
    if group_id is not None:
        payload["group_id"] = group_id
    return payload
