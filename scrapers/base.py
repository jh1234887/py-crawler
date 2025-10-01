from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional

import requests
from bs4 import BeautifulSoup

from ..config import ScrapingSource

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0 Safari/537.36"
    )
}


@dataclass
class Article:
    title: str
    link: str
    content: str
    summary: str | None = None
    author: str | None = None
    category: str | None = None
    pubdate: str | None = None
    meta: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        payload = {
            "title": self.title,
            "link": self.link,
            "content": self.content,
        }
        if self.summary:
            payload["summary"] = self.summary
        if self.author:
            payload["author"] = self.author
        if self.category:
            payload["category"] = self.category
        if self.pubdate:
            payload["pubdate"] = self.pubdate
        if self.meta:
            payload["meta"] = self.meta
        return payload


class BaseScraper(ABC):
    def __init__(
        self,
        session: Optional[requests.Session] = None,
        delay: float = 0.5,
        timeout: int = 10,
    ) -> None:
        self.session = session or requests.Session()
        self.delay = delay
        self.timeout = timeout

    def fetch(self, url: str) -> BeautifulSoup:
        response = self.session.get(url, headers=DEFAULT_HEADERS, timeout=self.timeout)
        response.raise_for_status()
        return BeautifulSoup(response.content, "html.parser")

    def sleep(self) -> None:
        if self.delay:
            time.sleep(self.delay)

    @abstractmethod
    def collect(self, source: ScrapingSource, *, start_page: int, end_page: int | None) -> List[Article]:
        raise NotImplementedError


ScraperResult = List[Article]


__all__ = ["Article", "BaseScraper", "ScraperResult", "DEFAULT_HEADERS"]
