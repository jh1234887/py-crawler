from __future__ import annotations

from typing import List
from urllib.parse import urlparse

import requests

from ..config import ScrapingSource
from ..utils import clean_article_node, ensure_absolute
from . import register_scraper
from .base import Article, BaseScraper


@register_scraper("foodtoday")
class FoodTodayScraper(BaseScraper):
    """Scraper for 푸드투데이."""

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

            items = soup.select('ul.art_list_all > li')
            if not items:
                break

            for index, item in enumerate(items, start=1):
                link_element = item.select_one('a')
                if not link_element or 'href' not in link_element.attrs:
                    continue
                href = link_element['href']
                article_url = ensure_absolute(href, base_url)

                title_element = item.select_one('h2')
                if not title_element:
                    continue
                title = title_element.get_text(strip=True)

                summary_element = item.select_one('p.ffd')
                summary = summary_element.get_text(strip=True) if summary_element else None

                author = pubdate = None
                info_items = item.select('ul.art_info > li')
                if len(info_items) >= 2:
                    author = info_items[0].get_text(strip=True) or None
                    pubdate = info_items[1].get_text(strip=True) or None

                content = summary or ""
                try:
                    article_soup = self.fetch(article_url)
                except requests.RequestException:
                    pass
                else:
                    article_node = (
                        article_soup.select_one('div.article_body')
                        or article_soup.select_one('div.art_body')
                        or article_soup.select_one('div.content')
                        or article_soup.select_one('article')
                    )
                    extracted = clean_article_node(article_node)
                    if extracted:
                        content = extracted

                articles.append(
                    Article(
                        title=title,
                        link=article_url,
                        content=content,
                        summary=summary,
                        author=author,
                        pubdate=pubdate,
                        meta={"page": page_num, "index": index},
                    )
                )

                self.sleep()

            self.sleep()

        return articles
