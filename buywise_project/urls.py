from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("agent.urls")),
    # Serve the frontend SPA
    path("", TemplateView.as_view(template_name="index.html")),
    path("chat/", TemplateView.as_view(template_name="chat.html")),
] + static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0])
