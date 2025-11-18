from django.urls import path
from .views import FrontendView, my_links_view, index_page, redirect_view

urlpatterns = [
    path("", FrontendView.as_view(), name="frontend"),
    path("", index_page, name="index"),
    path("my/links/", my_links_view, name="my-links"),
    path("r/<str:short_code>/", redirect_view, name="redirect_public"),
]