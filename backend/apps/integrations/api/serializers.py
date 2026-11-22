from rest_framework import serializers


class ConnectionSerializer(serializers.Serializer):
    account_email = serializers.EmailField()
    connected_at = serializers.DateTimeField(source="created_at")


class IntegrationStatusSerializer(serializers.Serializer):
    id = serializers.CharField(source="integration.id")
    name = serializers.CharField(source="integration.name")
    description = serializers.CharField(source="integration.description")
    configured = serializers.BooleanField()
    connection = ConnectionSerializer(allow_null=True)
