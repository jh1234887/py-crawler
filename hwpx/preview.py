from __future__ import annotations

import asyncio
from typing import List
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

try:
    from crawl4ai import AsyncWebCrawler
except ImportError:  # pragma: no cover
    AsyncWebCrawler = None  # type: ignore

from .parsers import extract_preview_urls, normalize_preview_urls


async def _render_with_crawl4ai(url: str) -> str:
    if AsyncWebCrawler is None:
        raise RuntimeError("crawl4ai 패키지를 찾을 수 없습니다.")
    async with AsyncWebCrawler() as crawler:  # type: ignore[call-arg]
        result = crawler.arun(url)
        if asyncio.iscoroutine(result):
            result = await result
    return getattr(result, "html", "") or ""


def _render_html(url: str) -> str:
    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(_render_with_crawl4ai(url))
    except RuntimeError:
        raise
    except Exception:
        return ""
    finally:
        asyncio.set_event_loop(None)
        loop.close()


def collect_preview_urls(page_url: str) -> List[str]:
    base = urlparse(page_url)
    base_url = f"{base.scheme}://{base.netloc}"

    html = ""
    try:
        html = _render_html(page_url)
    except RuntimeError:
        html = ""

    soup: BeautifulSoup | None = None
    if html:
        soup = BeautifulSoup(html, "html.parser")

    urls: List[str] = []
    if soup:
        urls = extract_preview_urls(soup, base_url, page_url)

    if not urls:
        try:
            response = requests.get(page_url, timeout=10)
            response.raise_for_status()
        except requests.RequestException:
            return []
        soup = BeautifulSoup(response.content, "html.parser")
        urls = extract_preview_urls(soup, base_url, page_url)

    return normalize_preview_urls(urls)


__all__ = ["collect_preview_urls"]
