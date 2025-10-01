from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional
from urllib import request

import feedparser

from ..config import RssSource

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0 Safari/537.36"
    )
}


@dataclass
class RssArticle:
    title: str
    link: str
    summary: Optional[str] = None
    published: Optional[str] = None
    raw: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        payload = {
            "title": self.title,
            "link": self.link,
        }
        if self.summary:
            payload["summary"] = self.summary
        if self.published:
            payload["published"] = self.published
        if self.raw:
            payload["raw"] = self.raw
        return payload


class RssCollector:
    def __init__(self, *, delay: float = 0.0) -> None:
        self.delay = delay

    def collect(self, source: RssSource) -> List[RssArticle]:
        req = request.Request(source.url, headers=DEFAULT_HEADERS)
        if source.encoding:
            req.add_header("Accept-Charset", source.encoding)

        try:
            with request.urlopen(req) as resp:
                feed = feedparser.parse(resp)
        except Exception as exc:
            print(f"[rss] 요청 실패 ({source.url}): {exc}")
            return []

        if getattr(feed, "bozo", False):
            print(f"[rss] 파싱 오류 ({source.url}): {getattr(feed, 'bozo_exception', '')}")
            return []

        articles: List[RssArticle] = []
        for entry in feed.entries:
            title = getattr(entry, "title", None)
            link = getattr(entry, "link", None)
            if not title or not link:
                continue
            article = RssArticle(
                title=title,
                link=link,
                summary=getattr(entry, "summary", None),
                published=getattr(entry, "published", None),
            )
            articles.append(article)
            if self.delay:
                time.sleep(self.delay)
        return articles


__all__ = ["RssCollector", "RssArticle"]
