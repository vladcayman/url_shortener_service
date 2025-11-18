"""
URL configuration for shortener_project project.

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
from django.contrib import admin
from django.urls import path, include

from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from shortener.views import redirect_view, FrontendView, my_links_view, index_page

urlpatterns = [
    # Главная страница с формой
    path("", FrontendView.as_view(), name="frontend"),
    path("", index_page, name="index"),
    path("my/links/", my_links_view, name="my-links"),

    # Админка
    path("admin/", admin.site.urls),

    # OpenAPI + Swagger
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="docs"),

    # JWT
    path("api/v1/auth/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/v1/auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),

    # API v1
    path("api/v1/", include(("shortener.api.urls", "shortener"), namespace="v1")),

    # публичный редирект без префикса
    path("r/<str:short_code>/", redirect_view, name="redirect_public"),
]