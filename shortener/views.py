from .filters import LinkFilter
from urllib import request as urlreq, error as urlerr
from django.db.models import F, Count
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import extend_schema

from rest_framework import viewsets, permissions, decorators, response, status
from rest_framework.views import APIView

from django.shortcuts import render
from django.contrib.auth.decorators import login_required

from .models import Link, Category, Tag, ClickEvent
from .serializers import (
    LinkSerializer, CategorySerializer, TagSerializer, PublicShortenSerializer
)
from .permissions import IsOwner
from .utils import generate_short_code, detect_device

from django.views.generic import TemplateView


class LinkViewSet(viewsets.ModelViewSet):
    serializer_class = LinkSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwner]
    filterset_class = LinkFilter

    def get_queryset(self):
        return Link.objects.filter(owner=self.request.user).select_related("category").prefetch_related("tags")

    def perform_create(self, serializer):
        # Генерируем short_code
        serializer.save(short_code=generate_short_code())

    @decorators.action(detail=True, methods=["post"])
    def check_alive(self, request, pk=None):
        link = self.get_object()
        try:
            req = urlreq.Request(link.original_url, method="HEAD")
            with urlreq.urlopen(req, timeout=8) as r:
                status_code = r.getcode()
            is_alive = 200 <= status_code < 400
        except urlerr.URLError:
            status_code = None
            is_alive = False

        link.is_alive = is_alive
        link.last_check_status = status_code
        link.last_checked_at = timezone.now()
        link.save(update_fields=["is_alive", "last_check_status", "last_checked_at"])
        return response.Response(
            {"is_alive": is_alive, "status": status_code, "checked_at": link.last_checked_at},
            status=status.HTTP_200_OK,
        )

    @decorators.action(detail=True, methods=["get"])
    def stats(self, request, pk=None):
        link = self.get_object()
        # Простая агрегация: клики по дням
        by_day = (
            ClickEvent.objects.filter(link=link)
            .extra(select={"day": "date(occurred_at)"})
            .values("day")
            .order_by("day")
            .annotate(count=Count("id"))
        )
        return response.Response(
            {"clicks_total": link.clicks_count, "by_day": list(by_day)},
            status=status.HTTP_200_OK,
        )

class CategoryViewSet(viewsets.ModelViewSet):
    serializer_class = CategorySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Category.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

class TagViewSet(viewsets.ModelViewSet):
    serializer_class = TagSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Tag.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

class PublicShorten(APIView):
    """
    Публичный эндпоинт: создать короткую ссылку без авторизации
    """
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        request=PublicShortenSerializer,       # что отправляем
        responses={201: LinkSerializer},       # что получаем
    )
    def post(self, request):
        s = PublicShortenSerializer(data=request.data)
        s.is_valid(raise_exception=True)

        code = generate_short_code()
        link = Link.objects.create(
            owner=None,
            original_url=s.validated_data["original_url"],
            short_code=code,
            title=s.validated_data.get("title", ""),
        )

        return response.Response(
            data={
                "short_code": code,
                "short_url": f"/r/{code}",
                "original_url": link.original_url,
            },
            status=status.HTTP_201_CREATED,
        )

def redirect_view(request, short_code: str):
    """
    Публичный редирект + лог клика
    """
    link = get_object_or_404(Link, short_code=short_code)

    Link.objects.filter(pk=link.pk).update(clicks_count=F("clicks_count") + 1)

    ua = request.META.get("HTTP_USER_AGENT", "")
    device, os, browser = detect_device(ua)

    ClickEvent.objects.create(
        link=link,
        referrer=request.META.get("HTTP_REFERER", "")[:1000],
        user_agent=ua[:1000],
        device_type=device,
        os=os,
        browser=browser,
        ip_address=request.META.get("REMOTE_ADDR"),
    )
    return HttpResponseRedirect(link.original_url)


class FrontendView(TemplateView):
    template_name = "shortener/index.html"

@login_required
def my_links_view(request):
    links = (
        Link.objects.all()
        .select_related("category")
        .prefetch_related("tags")
        .order_by("-created_at")
    )
    return render(request, "shortener/my_links.html", {"links": links})

def index_page(request):
    """
    Простой рендер главной страницы с формой сокращения ссылок
    """
    return render(request, "shortener/index.html")
