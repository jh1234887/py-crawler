from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

import feedparser
import requests

from ..config import RssSource
from ..scrapers.base import DEFAULT_HEADERS
from .content_fetcher import ArticleContentFetcher


@dataclass
class RssArticle:
    title: str
    link: str
    content: str
    summary: Optional[str] = None
    published: Optional[str] = None
    raw: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        payload = {
            "title": self.title,
            "link": self.link,
            "content": self.content,
        }
        if self.summary:
            payload["summary"] = self.summary
        if self.published:
            payload["published"] = self.published
        if self.raw:
            payload["raw"] = self.raw
        return payload


class RssCollector:
    def __init__(
        self,
        *,
        delay: float = 0.0,
        timeout: int = 10,
        session: Optional[requests.Session] = None,
        fetch_content: bool = True,
        content_timeout: int = 30,
        content_retry_attempts: int = 2,
        content_retry_delay: float = 1.0,
        content_delay: Optional[float] = None,
        max_articles_per_source: Optional[int] = None,
    ) -> None:
        self.session = session or requests.Session()
        self.delay = delay
        self.timeout = timeout
        self.fetch_content = fetch_content
        self.max_articles_per_source = max_articles_per_source
        self.content_delay = content_delay if content_delay is not None else delay
        self.content_fetcher = (
            ArticleContentFetcher(
                session=self.session,
                timeout=content_timeout,
                max_retries=content_retry_attempts,
                retry_delay=content_retry_delay,
                delay=self.content_delay,
            )
            if fetch_content
            else None
        )

    def collect(self, source: RssSource, *, limit: Optional[int] = None) -> List[RssArticle]:
        effective_limit = self._resolve_limit(limit)

        try:
            response = self.session.get(source.url, headers=DEFAULT_HEADERS, timeout=self.timeout)
            response.raise_for_status()
            if source.encoding:
                response.encoding = source.encoding
            feed = feedparser.parse(response.content)
        except Exception as exc:
            print(f"[rss] 요청 실패 ({source.url}): {exc}")
            return []

        if getattr(feed, "bozo", False):
            print(f"[rss] 파싱 오류 ({source.url}): {getattr(feed, 'bozo_exception', '')}")
            return []

        base_url = response.url
        articles: List[RssArticle] = []
        for entry in feed.entries:
            title = getattr(entry, "title", None)
            link = getattr(entry, "link", None)
            if not title or not link:
                continue
            resolved_link = self._resolve_link(link, base_url)
            if not resolved_link:
                continue
            article = RssArticle(
                title=title,
                link=resolved_link,
                content=self._fetch_article_content(resolved_link, source.encoding),
                summary=getattr(entry, "summary", None),
                published=getattr(entry, "published", None),
            )
            articles.append(article)
            if self.delay:
                time.sleep(self.delay)
            if effective_limit is not None and len(articles) >= effective_limit:
                break
        return articles

    def _resolve_limit(self, limit: Optional[int]) -> Optional[int]:
        if self.max_articles_per_source is None:
            return limit
        if limit is None:
            return self.max_articles_per_source
        return min(limit, self.max_articles_per_source)

    def _resolve_link(self, link: str, base_url: str) -> Optional[str]:
        if not link:
            return None
        resolved = urljoin(base_url, link)
        if resolved.startswith(("http://", "https://")):
            return resolved
        return None

    def _fetch_article_content(self, url: str, encoding: Optional[str]) -> str:
        if not self.fetch_content or not self.content_fetcher:
            return ""
        content = self.content_fetcher.fetch(url, encoding=encoding)
        return content or ""


__all__ = ["RssCollector", "RssArticle"]
