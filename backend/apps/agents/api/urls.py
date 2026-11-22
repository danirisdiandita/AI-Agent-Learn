from django.urls import path

from . import views

urlpatterns = [
    path("chat/", views.chat, name="agents_chat"),
    path("sessions/", views.chat_sessions, name="agents_chat_sessions"),
    path("sessions/<int:session_id>/", views.chat_session, name="agents_chat_session"),
    path("sessions/<int:session_id>/messages/", views.chat_messages, name="agents_chat_messages"),
]
