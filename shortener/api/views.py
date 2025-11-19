from urllib import request as urlreq, error as urlerr

from django.db.models import Count
from django.utils import timezone

from drf_spectacular.utils import extend_schema
from rest_framework import viewsets, permissions, decorators, response, status
from rest_framework.views import APIView

from django.core.cache import cache

from ..filters import LinkFilter
from ..models import Link, Category, Tag, ClickEvent
from ..serializers import (
    LinkSerializer,
    CategorySerializer,
    TagSerializer,
    PublicShortenSerializer,
)
from ..permissions import IsOwner
from ..utils import generate_short_code

class LinkViewSet(viewsets.ModelViewSet):
    serializer_class = LinkSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwner]
    filterset_class = LinkFilter

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Link.objects.none()

        return (
            Link.objects
            .filter(owner=self.request.user)
            .select_related("category")
            .prefetch_related("tags")
        )

    def perform_create(self, serializer):
        # создаём ссылку с owner
        link = serializer.save(
            owner=self.request.user,
            short_code=generate_short_code()
        )

        # кладём ссылку в кэш
        cache.set(
            f"link:{link.short_code}",
            {"id": link.id, "original_url": link.original_url},
            timeout=300,
        )

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
        link.save(
            update_fields=[
                "is_alive",
                "last_check_status",
                "last_checked_at",
            ]
        )
        return response.Response(
            {
                "is_alive": is_alive,
                "status": status_code,
                "checked_at": link.last_checked_at,
            },
            status=status.HTTP_200_OK,
        )

    @decorators.action(detail=True, methods=["get"])
    def stats(self, request, pk=None):
        link = self.get_object()
        by_day = (
            ClickEvent.objects.filter(link=link)
            .extra(select={"day": "date(occurred_at)"})
            .values("day")
            .order_by("day")
            .annotate(count=Count("id"))
        )
        return response.Response(
            {
                "clicks_total": link.clicks_count,
                "by_day": list(by_day),
            },
            status=status.HTTP_200_OK,
        )


class CategoryViewSet(viewsets.ModelViewSet):
    serializer_class = CategorySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Category.objects.none()

        return Category.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

class TagViewSet(viewsets.ModelViewSet):
    serializer_class = TagSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Tag.objects.none()

        return Tag.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

class PublicShorten(APIView):
    """
    Публичный эндпоинт: создать короткую ссылку без авторизации
    """
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        request=PublicShortenSerializer,
        responses={201: LinkSerializer},
    )
    def post(self, request):
        s = PublicShortenSerializer(data=request.data)
        s.is_valid(raise_exception=True)

        code = generate_short_code()

        # если пользователь авторизован, то привяжем ссылку к нему
        owner = request.user if request.user.is_authenticated else None

        link = Link.objects.create(
            owner=owner,
            original_url=s.validated_data["original_url"],
            short_code=code,
            title=s.validated_data.get("title", "") or "",
        )

        cache.set(
            f"link:{link.short_code}",
            {"id": link.id, "original_url": link.original_url},
            timeout=300,
        )

        return response.Response(
            data={
                "short_code": code,
                "short_url": f"/r/{code}",
                "original_url": link.original_url,
            },
            status=status.HTTP_201_CREATED,
        )