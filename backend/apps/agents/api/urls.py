from django.urls import path

from . import views

urlpatterns = [
    path("sessions/", views.chat_sessions, name="agents_chat_sessions"),
    path("sessions/<int:session_id>/", views.chat_session, name="agents_chat_session"),
    path("sessions/<int:session_id>/messages/", views.chat_messages, name="agents_chat_messages"),
    path("sessions/<int:session_id>/reply/", views.chat_reply, name="agents_chat_reply"),
    path("tool-calls/<int:call_id>/decision/", views.tool_call_decision, name="agents_tool_call_decision"),
]
