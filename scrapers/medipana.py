from __future__ import annotations

from typing import List
from urllib.parse import urlparse

import requests

from ..config import ScrapingSource
from ..utils import clean_article_node, ensure_absolute
from . import register_scraper
from .base import Article, BaseScraper


@register_scraper("medipana")
class MedipanaScraper(BaseScraper):
    """Scraper for 메디파나뉴스."""

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

            items = soup.select('div.lst_feature1 > ul > li')
            if not items:
                break

            for index, item in enumerate(items, start=1):
                link_node = item.select_one('a')
                if not link_node or 'href' not in link_node.attrs:
                    continue
                href = link_node['href'].lstrip('./')
                article_url = ensure_absolute(href, base_url)

                title_node = item.select_one('div.tx p.h1')
                if not title_node:
                    continue
                title = title_node.get_text(strip=True)

                tit_div = item.select_one('div.tit')
                category = author = pubdate = None
                if tit_div:
                    paragraphs = tit_div.select('p')
                    if len(paragraphs) >= 1:
                        category = paragraphs[0].get_text(strip=True) or None
                    if len(paragraphs) >= 2:
                        author = paragraphs[1].get_text(strip=True) or None
                    if len(paragraphs) >= 3:
                        pubdate = paragraphs[2].get_text(strip=True) or None

                summary_node = item.select_one('div.tx p.t1')
                summary = summary_node.get_text(strip=True) if summary_node else None

                content = summary or ""
                try:
                    article_soup = self.fetch(article_url)
                except requests.RequestException:
                    pass
                else:
                    article_node = (
                        article_soup.select_one('div.article_view')
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
                        category=category,
                        author=author,
                        pubdate=pubdate,
                        meta={"page": page_num, "index": index},
                    )
                )

                self.sleep()

            self.sleep()

        return articles
