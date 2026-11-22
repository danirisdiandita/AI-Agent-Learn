"""Read queries for integrations."""

from dataclasses import dataclass

from .catalog import INTEGRATIONS, Integration
from .models import Connection


@dataclass(frozen=True)
class IntegrationStatus:
    integration: Integration
    configured: bool
    connection: Connection | None


def integration_statuses(*, user) -> list[IntegrationStatus]:
    """Every integration in the catalog, with the user's connection to it if one exists."""
    # The list never shows tokens, so it skips loading and decrypting them.
    connections = {
        connection.provider: connection
        for connection in Connection.objects.filter(user=user).defer("access_token", "refresh_token")
    }
    return [
        IntegrationStatus(
            integration=integration,
            configured=integration.oauth_client() is not None,
            connection=connections.get(integration.provider),
        )
        for integration in INTEGRATIONS.values()
    ]
