from .services import unread_chat_count


def unread_chats(request):
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return {}
    return {"unread_chats": unread_chat_count(user)}
