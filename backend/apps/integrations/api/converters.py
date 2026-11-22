from ..catalog import INTEGRATIONS


class IntegrationConverter:
    """Matches an integration ID from the catalog, so an unknown ID is a 404 before any view runs."""

    regex = "[a-z0-9-]+"

    def to_python(self, value):
        if value not in INTEGRATIONS:
            raise ValueError(value)
        return INTEGRATIONS[value]

    def to_url(self, integration):
        return integration.id
