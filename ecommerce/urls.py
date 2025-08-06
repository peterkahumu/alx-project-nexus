"""
URL configuration for ecommerce project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.http import HttpResponse
from drf_yasg import openapi
from drf_yasg.views import get_schema_view
from rest_framework import permissions


def home(request):
    """Welcome message"""
    return HttpResponse(
        """
        <h1>Welcome to Alx Project Nexus Ecommerce API</h1>
        <p>API Documentation:</p>
        <ul>
            <li><a href="/swagger/">Swagger UI</a> - Interactive API documentation</li>
            <li><a href="/redoc/">ReDoc</a> - Alternative API documentation</li>
            <li><a href="/admin/">Admin Panel</a> - Admin interface</li>
        </ul>
        """,
        content_type="text/html",
    )


# Schema View Configuration
schema_view = get_schema_view(
    openapi.Info(
        title="Alx Project Nexus API Documentation",
        default_version="v1",
        description="Project Nexus Ecommerce Documentation",
        terms_of_service="https://www.yourapp.com/terms/",
        contact=openapi.Contact(email="contact@yourapp.com"),
        license=openapi.License(name="MIT License"),
    ),
    public=True,
    permission_classes=(permissions.AllowAny,),
    authentication_classes=[],
)


# URL patterns
urlpatterns = [
    path("", home, name="home"),
    path("admin/", admin.site.urls),
    
    # OpenAPI Schema
    path(
        "swagger<format>/", 
        schema_view.without_ui(cache_timeout=0), 
        name="schema-json"
    ),
    
    # Swagger UI
    path(
        "swagger/",
        schema_view.with_ui("swagger", cache_timeout=0),
        name="schema-swagger-ui",
    ),
    
    # ReDoc
    path(
        "redoc/", 
        schema_view.with_ui("redoc", cache_timeout=0),
        name="schema-redoc"
    ),
    
    # App URLs
    path("api/users/", include("users.urls")),
    path("api/", include("products.urls")),
    path("api/", include("cart.urls")),
]


urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
