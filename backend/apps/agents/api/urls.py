from django.urls import path

from . import views

urlpatterns = [
    path("chat/", views.chat, name="agents_chat"),
]
