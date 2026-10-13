from django.urls import path

from . import views

app_name = "chat"

urlpatterns = [
    path("", views.inbox, name="inbox"),
    path("upload/", views.upload_api, name="upload_api"),
    path("groups/new/", views.group_create, name="group_create"),
    path("groups/<int:group_id>/", views.group_conversation, name="group_conversation"),
    path(
        "groups/<int:group_id>/messages/",
        views.group_messages_api,
        name="group_messages_api",
    ),
    path("groups/<int:group_id>/mute/", views.group_mute_api, name="group_mute"),
    path(
        "groups/<int:group_id>/members/",
        views.group_members_api,
        name="group_members",
    ),
    path("groups/<int:group_id>/leave/", views.group_leave_api, name="group_leave"),
    path("groups/<int:group_id>/delete/", views.group_delete_api, name="group_delete"),
    path("api/<int:user_id>/", views.messages_api, name="messages_api"),
    path("<int:user_id>/mute/", views.mute_api, name="mute"),
    path("<int:user_id>/delete/", views.conversation_delete_api, name="conversation_delete"),
    path("<int:user_id>/", views.conversation, name="conversation"),
]
