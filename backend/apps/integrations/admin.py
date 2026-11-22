from django.contrib import admin

from .models import Connection


@admin.register(Connection)
class ConnectionAdmin(admin.ModelAdmin):
    """Shows who connected what and lets an admin remove a connection. Tokens never appear here."""

    list_display = ("user", "provider", "account_email", "created_at", "updated_at")
    list_filter = ("provider",)
    search_fields = ("user__email", "account_email")
    fields = ("user", "provider", "account_email", "scopes", "access_token_expires_at", "created_at", "updated_at")
    readonly_fields = fields

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("user").defer("access_token", "refresh_token")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
