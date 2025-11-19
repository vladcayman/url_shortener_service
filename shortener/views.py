from django.db.models import F
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.contrib.auth.decorators import login_required
from django.views.generic import TemplateView

from .models import Link, ClickEvent
from .utils import detect_device

from django.core.cache import cache


def redirect_view(request, short_code: str):
    """
    Публичный редирект + лог клика
    """

    cache_key = f"link:{short_code}"
    data = cache.get(cache_key)

    if data is None:
        link = get_object_or_404(Link, short_code=short_code)
        data = {
            "id": link.id,
            "original_url": link.original_url,
        }
        # кладём в кэш
        cache.set(cache_key, data, timeout=300)

    link_id = data["id"]
    original_url = data["original_url"]

    Link.objects.filter(pk=link_id).update(clicks_count=F("clicks_count") + 1)

    ua = request.META.get("HTTP_USER_AGENT", "")
    device, os, browser = detect_device(ua)

    ClickEvent.objects.create(
        link_id=link_id,
        referrer=request.META.get("HTTP_REFERER", "")[:1000],
        user_agent=ua[:1000],
        device_type=device,
        os=os,
        browser=browser,
        ip_address=request.META.get("REMOTE_ADDR"),
    )
    return HttpResponseRedirect(original_url)


class FrontendView(TemplateView):
    template_name = "shortener/index.html"

@login_required
def my_links_view(request):
    links = (
        Link.objects
        .filter(owner=request.user)
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
