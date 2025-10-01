from __future__ import annotations

from typing import List, Optional
from urllib.parse import urlparse

import requests

from ..config import ScrapingSource
from ..utils import clean_article_node, ensure_absolute
from . import register_scraper
from .base import Article, BaseScraper


@register_scraper("consumernews")
class ConsumerNewsScraper(BaseScraper):
    """Scraper for 소비자가만드는신문 with multiple layout fallbacks."""

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
            if "{}" not in source.url:
                if page_num > 1:
                    break
                list_url = source.url
            else:
                if "nStart" in source.url:
                    page_param = (page_num - 1) * 10
                else:
                    page_param = page_num
                list_url = source.url.format(page_param)

            try:
                soup = self.fetch(list_url)
            except requests.RequestException:
                continue

            layout, items = self._detect_layout(soup)
            if not items:
                break

            for index, item in enumerate(items, start=1):
                article = self._parse_item(item, layout, base_url)
                if not article:
                    continue

                title, article_url, summary, pubdate, category = article
                content = summary or ""

                try:
                    article_soup = self.fetch(article_url)
                except requests.RequestException:
                    pass
                else:
                    article_node = (
                        article_soup.select_one('div.user-snp')
                        or article_soup.select_one('div.entry-content')
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

    @staticmethod
    def _detect_layout(soup) -> tuple[str | None, list]:
        nutradex_table = soup.select_one('td[style*="padding:8px 10px 8px 10px"] > table')
        if nutradex_table:
            items = [
                c
                for c in nutradex_table.select('tr > td[width="580px"]')
                if c.find('table') and c.find('strong', id='news_title')
            ]
            if items:
                return "nutradex", items

        raven_items = soup.select('div.raven-post-item')
        if raven_items:
            return "raven", raven_items

        list_blocks = soup.select('div.list-block')
        if list_blocks:
            return "list-block", list_blocks

        return None, []

    @staticmethod
    def _parse_item(item, layout: str | None, base_url: str) -> Optional[tuple[str, str, Optional[str], Optional[str], Optional[str]]]:
        if layout == "nutradex":
            inner = item.find('table')
            if inner is None:
                return None
            title_node = inner.select_one('strong#news_title')
            link_node = inner.select_one('a[href*="/news/news.html?mode=view"]')
            date_node = inner.select_one('span#news_date')
            summary_node = inner.select_one('span#news_summary')

            if not title_node or not link_node:
                return None

            title = title_node.get_text(strip=True)
            href = link_node.get('href', '').replace('&amp;', '&')
            article_url = ensure_absolute(href, base_url)
            pubdate = date_node.get_text(strip=True).strip('[]') if date_node else None
            summary = summary_node.get_text(strip=True) if summary_node else None
            category = None
            return title, article_url, summary, pubdate, category

        if layout == "raven":
            title_node = item.select_one('h5.raven-post-title a, a.raven-post-title-link')
            if not title_node:
                return None
            article_url = ensure_absolute(title_node.get('href', ''), base_url)
            title = title_node.get_text(strip=True)
            date_node = item.select_one('a.raven-post-date')
            summary_node = item.select_one('div.raven-post-excerpt')
            pubdate = date_node.get_text(strip=True) if date_node else None
            summary = summary_node.get_text(strip=True) if summary_node else None
            category = None
            return title, article_url, summary, pubdate, category

        if layout == "list-block":
            title_node = item.select_one('div.list-titles a strong')
            link_node = item.select_one('div.list-titles a')
            date_node = item.select_one('div.list-dated')
            summary_node = item.select_one('p.list-summary a')

            if not title_node or not link_node:
                return None

            title = title_node.get_text(strip=True)
            href = link_node.get('href', '')
            article_url = ensure_absolute(href, base_url)

            pubdate = None
            category = None
            if date_node:
                date_text = date_node.get_text(strip=True)
                parts = [part.strip() for part in date_text.split('|') if part.strip()]
                if parts:
                    category = parts[0]
                if len(parts) >= 3:
                    pubdate = parts[-1]
                elif len(parts) == 2:
                    pubdate = parts[1]
            summary = summary_node.get_text(strip=True) if summary_node else None
            return title, article_url, summary, pubdate, category

        return None
