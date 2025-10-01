from __future__ import annotations

import asyncio
from typing import Iterable, Dict

from bs4 import BeautifulSoup

try:
    from crawl4ai import AsyncWebCrawler
except ImportError:  # pragma: no cover - optional dependency guard
    AsyncWebCrawler = None  # type: ignore


def _require_crawl4ai() -> None:
    if AsyncWebCrawler is None:
        raise RuntimeError(
            "crawl4ai.AsyncWebCrawler를 사용할 수 없습니다. 패키지가 설치되어 있는지 확인하세요."
        )


async def _render_many_async(urls: Iterable[str]) -> Dict[str, str]:
    _require_crawl4ai()
    async with AsyncWebCrawler() as crawler:  # type: ignore[call-arg]
        results: Dict[str, str] = {}
        for url in urls:
            try:
                response = await crawler.arun(url)
            except Exception:
                html = ""
            else:
                html = getattr(response, "html", "") or ""
            results[url] = html
        return results


def render_html(url: str) -> str:
    rendered = render_many([url])
    return rendered.get(url, "")


def render_many(urls: Iterable[str]) -> Dict[str, str]:
    urls = list(urls)
    if not urls:
        return {}
    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(_render_many_async(urls))
    finally:
        asyncio.set_event_loop(None)
        loop.close()


def render_soup(url: str) -> BeautifulSoup | None:
    html = render_html(url)
    if not html:
        return None
    return BeautifulSoup(html, "html.parser")


__all__ = ["render_html", "render_many", "render_soup"]
