from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/auth/", include("apps.accounts.api.urls")),
    path("api/v1/agents/", include("apps.agents.api.urls")),
    path("api/v1/integrations/", include("apps.integrations.api.urls")),
    # new-backend-app: urls above
]
