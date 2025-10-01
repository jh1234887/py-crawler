from __future__ import annotations

from typing import List
from urllib.parse import urlparse

import requests

from ..config import ScrapingSource
from ..utils import clean_article_node, ensure_absolute
from . import register_scraper
from .base import Article, BaseScraper


@register_scraper("cucs")
class CucsScraper(BaseScraper):
    """Scraper for 소비자주권시민회의 with multiple layout fallbacks."""

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

            items = []
            layout = None

            nutradex_table = soup.select_one('td[style*="padding:8px 10px 8px 10px"] > table')
            if nutradex_table:
                layout = "nutradex"
                items = [
                    c
                    for c in nutradex_table.select('tr > td[width="580px"]')
                    if c.find('table') and c.find('strong', id='news_title')
                ]
            else:
                raven = soup.select('div.raven-post-item')
                if raven:
                    layout = "raven"
                    items = raven

            if not items:
                break

            for index, item in enumerate(items, start=1):
                if layout == "nutradex":
                    inner = item.find('table')
                    if inner is None:
                        continue
                    title_node = inner.select_one('strong#news_title')
                    link_node = inner.select_one('a[href*="/news/news.html?mode=view"]')
                    date_node = inner.select_one('span#news_date')
                    summary_node = inner.select_one('span#news_summary')

                    if not title_node or not link_node:
                        continue

                    title = title_node.get_text(strip=True)
                    href = link_node.get('href', '').replace('&amp;', '&')
                    article_url = ensure_absolute(href, base_url)
                    pubdate = date_node.get_text(strip=True).strip('[]') if date_node else None
                    summary = summary_node.get_text(strip=True) if summary_node else None
                    category = None
                else:  # raven
                    title_node = item.select_one('h5.raven-post-title a')
                    if not title_node:
                        continue
                    article_url = ensure_absolute(title_node.get('href', ''), base_url)
                    title = title_node.get_text(strip=True)
                    date_node = item.select_one('a.raven-post-date')
                    summary_node = item.select_one('div.raven-post-excerpt')
                    pubdate = date_node.get_text(strip=True) if date_node else None
                    summary = summary_node.get_text(strip=True) if summary_node else None
                    category = None

                content = summary or ""
                try:
                    article_soup = self.fetch(article_url)
                except requests.RequestException:
                    pass
                else:
                    article_node = (
                        article_soup.select_one('div.entry-content')
                        or article_soup.select_one('article.post-content')
                        or article_soup.select_one('div.article_content')
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
                        pubdate=pubdate,
                        category=category,
                        meta={"page": page_num, "index": index, "layout": layout},
                    )
                )

                self.sleep()

            self.sleep()

        return articles
