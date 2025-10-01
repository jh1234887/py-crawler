from __future__ import annotations

from typing import List
from urllib.parse import urlparse

import requests
from ..config import ScrapingSource
from ..utils import clean_article_node, ensure_absolute
from . import register_scraper
from .base import Article, BaseScraper


@register_scraper("nutradex")
class NutradexScraper(BaseScraper):
    """Scraper supporting 기능식품신문 and nutradex-style layouts."""

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
            page_param = (page_num - 1) * 10 if "nStart" in source.url and "{}" in source.url else page_num
            list_url = source.url.format(page_param) if "{}" in source.url else source.url
            try:
                soup = self.fetch(list_url)
            except requests.RequestException:
                continue

            main_table = soup.select_one('td[style*="padding:8px 10px 8px 10px"] > table')
            if not main_table:
                break

            containers = [
                container
                for container in main_table.select('tr > td[width="580px"]')
                if container.find('table') and container.find('strong', id='news_title')
            ]
            if not containers:
                break

            for index, container in enumerate(containers, start=1):
                inner_table = container.find('table')
                if inner_table is None:
                    continue
                title_element = inner_table.select_one('strong#news_title')
                link_element = inner_table.select_one('a[href*="/news/news.html?mode=view"]')
                date_element = inner_table.select_one('span#news_date')
                summary_element = inner_table.select_one('span#news_summary')

                if not title_element or not link_element:
                    continue

                title = title_element.get_text(strip=True)
                href = link_element.get('href', '').replace('&amp;', '&')
                article_url = ensure_absolute(href, base_url)
                pubdate = date_element.get_text(strip=True).strip('[]') if date_element else None
                summary = summary_element.get_text(strip=True) if summary_element else None

                content = summary or ""
                try:
                    article_soup = self.fetch(article_url)
                except requests.RequestException:
                    pass
                else:
                    article_node = (
                        article_soup.select_one('div.article_content')
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
                        meta={"page": page_num, "index": index},
                    )
                )

                self.sleep()

            self.sleep()

        return articles
