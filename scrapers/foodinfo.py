from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple
from urllib.parse import parse_qs, urlparse

from ..config import ScrapingSource
from ..utils import ensure_absolute
from . import register_scraper
from .base import Article, BaseScraper
from .foodinfo_crawl4ai import FoodInfoCrawler


@register_scraper("foodinfo")
class FoodInfoScraper(BaseScraper):
    """Wrapper that reuses the crawl4ai-assisted FoodInfo implementation."""

    def collect(
        self,
        source: ScrapingSource,
        *,
        start_page: int,
        end_page: int | None,
    ) -> List[Article]:
        detail_limit = int(source.raw.get("detail_limit", 10))
        last_page = end_page or source.max_pages
        if last_page < start_page:
            last_page = start_page

        seen: Dict[Tuple[str, object], Article] = {}
        for page_num in range(start_page, last_page + 1):
            list_url = self._build_list_url(source.url, page_num)
            crawler = FoodInfoCrawler(list_url=list_url, detail_limit=detail_limit, verbose=False)
            try:
                releases = crawler.run()
            except RuntimeError:
                continue

            for index, release in enumerate(releases, start=1):
                link = release.get("detail_url") or ""
                title = release.get("title") or ""
                if not link:
                    continue

                link = ensure_absolute(link, self._origin(list_url))
                number = release.get("number") if isinstance(release.get("number"), int) else None
                views = release.get("views") if isinstance(release.get("views"), int) else None
                content = release.get("content") or ""

                article = Article(
                    title=title,
                    link=link,
                    content=content or "",
                    summary=None,
                    pubdate=release.get("date"),
                    meta={
                        "page": page_num,
                        "index": index,
                        **({"number": number} if number is not None else {}),
                        **({"views": views} if views is not None else {}),
                    },
                )

                key: Tuple[str, object]
                if number is not None:
                    key = ("number", number)
                else:
                    key = ("link", link)
                if key not in seen:
                    seen[key] = article

            self.sleep()

        articles = list(seen.values())
        articles.sort(key=self._sort_key)
        return articles

    def _build_list_url(self, base_url: str, page_num: int) -> str:
        if "{}" in base_url:
            return base_url.format(page_num)
        if page_num <= 1:
            return base_url
        if "pageIndex=" in base_url:
            return re.sub(r"pageIndex=\d+", f"pageIndex={page_num}", base_url)
        separator = "&" if "?" in base_url else "?"
        return f"{base_url}{separator}pageIndex={page_num}"

    def _origin(self, url: str) -> str:
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}"

    def _sort_key(self, article: Article) -> Tuple[int, int, int]:
        meta = article.meta or {}
        number = meta.get("number") if isinstance(meta.get("number"), int) else None
        page = meta.get("page") if isinstance(meta.get("page"), int) else 0
        index = meta.get("index") if isinstance(meta.get("index"), int) else 0
        if number is not None:
            return (-number, page, index)
        return (page, index, 0)
