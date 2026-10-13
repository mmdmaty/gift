import math
import time

from django.conf import settings
from django.core.cache import cache


def get_client_ip(request):
    if settings.LOGIN_TRUST_CLOUDFLARE_IP:
        cf_ip = request.META.get("HTTP_CF_CONNECTING_IP")
        if cf_ip:
            return cf_ip.strip()
    return request.META.get("REMOTE_ADDR", "")


def _failures_key(ip):
    return f"login:failures:{ip}"


def _lock_key(ip):
    return f"login:locked:{ip}"


def lockout_remaining_seconds(ip):
    """Seconds left on this IP's ban, or 0 if it is not banned."""
    locked_until = cache.get(_lock_key(ip))
    if locked_until is None:
        return 0
    return max(0, math.ceil(locked_until - time.time()))


def failure_count(ip):
    return cache.get(_failures_key(ip), 0)


def register_failure(ip):
    """Record a failed attempt; ban the IP once it reaches the limit."""
    key = _failures_key(ip)
    window = settings.LOGIN_LOCKOUT_SECONDS
    cache.add(key, 0, window)
    try:
        failures = cache.incr(key)
    except ValueError:
        cache.set(key, 1, window)
        failures = 1

    if failures >= settings.LOGIN_MAX_ATTEMPTS:
        cache.set(_lock_key(ip), time.time() + window, window)
        cache.delete(key)


def clear_failures(ip):
    cache.delete(_failures_key(ip))

