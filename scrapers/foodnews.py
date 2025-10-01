from __future__ import annotations

from typing import List
from urllib.parse import urlparse

import requests
from bs4 import Tag

from ..config import ScrapingSource
from ..utils import clean_article_node
from . import register_scraper
from .base import Article, BaseScraper


@register_scraper("foodnews", "agrinet")
class FoodNewsScraper(BaseScraper):
    """Scraper for 식품저널."""

    def collect(
        self,
        source: ScrapingSource,
        *,
        start_page: int,
        end_page: int | None,
    ) -> List[Article]:
        articles: List[Article] = []
        parsed = urlparse(source.url)
        base_url = f"{parsed.scheme}://{parsed.netloc}"
        last_page = end_page or source.max_pages

        for page_num in range(start_page, last_page + 1):
            list_url = source.url.format(page_num) if "{}" in source.url else source.url
            try:
                soup = self.fetch(list_url)
            except requests.RequestException:
                continue

            container = soup.select_one("ul.type1")
            if not container:
                break

            for index, item in enumerate(container.select("li"), start=1):
                keyword = self._safe_text(item, "em.info.category")
                journalist = self._safe_text(item, "em.info.name")
                pubdate = self._safe_text(item, "em.info.dated")

                link = item.select_one("a")
                title = link.get_text(strip=True) if link else None
                href = link["href"] if link and "href" in link.attrs else None
                if not title or not href:
                    continue

                article_url = f"{base_url}{href}" if href.startswith("/") else href
                summary = None
                try:
                    article_soup = self.fetch(article_url)
                except requests.RequestException:
                    continue

                article_node = article_soup.select_one("article#article-view-content-div")
                content = clean_article_node(article_node) or "본문 추출 실패"

                articles.append(
                    Article(
                        title=title,
                        link=article_url,
                        content=content,
                        summary=summary,
                        author=journalist,
                        category=keyword,
                        pubdate=pubdate,
                        meta={"page": page_num, "index": index},
                    )
                )

                self.sleep()

            self.sleep()

        return articles

    @staticmethod
    def _safe_text(item: Tag, selector: str) -> str | None:
        target = item.select_one(selector)
        return target.get_text(strip=True) if target else None
