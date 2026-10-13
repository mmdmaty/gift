from django.core.cache import cache

PRESENCE_TTL = 45


def _key(user_id):
    return f"chat_online_{user_id}"


def add_connection(user_id):
    """Returns the new open-socket count for this user."""
    cache.add(_key(user_id), 0, timeout=PRESENCE_TTL)
    try:
        return cache.incr(_key(user_id))
    except ValueError:
        cache.set(_key(user_id), 1, timeout=PRESENCE_TTL)
        return 1


def remove_connection(user_id):
    """Returns the remaining open-socket count for this user."""
    try:
        return cache.decr(_key(user_id))
    except ValueError:
        return 0


def is_online(user_id):
    return (cache.get(_key(user_id)) or 0) > 0


def touch(user_id):
    """Refresh the expiry without changing the open-socket count."""
    count = cache.get(_key(user_id))
    if count:
        cache.set(_key(user_id), count, timeout=PRESENCE_TTL)
