from django.urls import re_path

from .consumers import ChatConsumer, GroupConsumer, NotifyConsumer

websocket_urlpatterns = [
    re_path(r"^ws/chat/group/(?P<group_id>\d+)/$", GroupConsumer.as_asgi()),
    re_path(r"^ws/chat/(?P<user_id>\d+)/$", ChatConsumer.as_asgi()),
    re_path(r"^ws/notify/$", NotifyConsumer.as_asgi()),
]
