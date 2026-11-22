"""HTTP endpoints for agents. Views parse the request, call a service or selector, and serialize the result."""

from rest_framework.decorators import api_view
from rest_framework.response import Response

from .. import services
from .serializers import ChatRequestSerializer


@api_view(["POST"])
def chat(request):
    serializer = ChatRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    try:
        message = services.chat(messages=serializer.validated_data["messages"])
    except services.ChatError as error:
        return Response({"detail": str(error)}, status=error.status)
    return Response({"message": message})
