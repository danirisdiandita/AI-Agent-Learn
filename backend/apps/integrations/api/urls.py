from django.urls import path, register_converter

from . import views
from .converters import IntegrationConverter

register_converter(IntegrationConverter, "integration")

urlpatterns = [
    path("", views.integration_list, name="integration_list"),
    path("<integration:integration>/", views.disconnect, name="integration_disconnect"),
    path("<integration:integration>/connect/", views.connect, name="integration_connect"),
    path("<integration:integration>/callback/", views.callback, name="integration_callback"),
]
