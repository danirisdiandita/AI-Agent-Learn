"""HTTP endpoints for integrations. Views parse the request, call a service or selector, and serialize the result."""

from urllib.parse import urlencode

from django.http import HttpResponseRedirect
from rest_framework import status
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .. import selectors, services
from .serializers import IntegrationStatusSerializer

# The dashboard screen that shows how a connection ended. Relative, so the browser stays on the origin
# that served the callback, which is the dashboard's own origin when its server proxies /api.
DASHBOARD_PATH = "/integrations"


@api_view(["GET"])
def integration_list(request):
    statuses = selectors.integration_statuses(user=request.user)
    return Response(IntegrationStatusSerializer(statuses, many=True).data)


@api_view(["POST"])
def connect(request, integration):
    try:
        url = services.start_connection(user=request.user, integration=integration)
    except services.NotConfigured as error:
        return Response({"detail": str(error)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    return Response({"authorization_url": url})


# The provider sends the browser here, so the request has no bearer token. The signed state names the user.
@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
def callback(request, integration):
    try:
        services.finish_connection(
            integration=integration,
            state=request.GET.get("state", ""),
            code=request.GET.get("code", ""),
            error=request.GET.get("error", ""),
        )
    except services.ConnectFailed as failed:
        return HttpResponseRedirect(f"{DASHBOARD_PATH}?{urlencode({'error': failed.failure})}")
    return HttpResponseRedirect(f"{DASHBOARD_PATH}?{urlencode({'connected': integration.id})}")


@api_view(["DELETE"])
def disconnect(request, integration):
    services.disconnect(user=request.user, integration=integration)
    return Response(status=status.HTTP_204_NO_CONTENT)
