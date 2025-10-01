from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence

import requests

from .config import CrawlerConfig, ScrapingSource
from .scrapers import get_scraper_for
from .scrapers.base import Article, BaseScraper


@dataclass
class CrawlerResult:
    source: ScrapingSource
    articles: List[Article]

    def to_dict(self) -> Dict[str, object]:
        return {
            "source": self.source.slug,
            "name": self.source.name,
            "articles": [article.to_dict() for article in self.articles],
        }


class Crawler:
    def __init__(
        self,
        config: CrawlerConfig,
        *,
        session: Optional[requests.Session] = None,
        delay: float = 0.5,
        timeout: int = 10,
    ) -> None:
        self.config = config
        self.session = session or requests.Session()
        self.delay = delay
        self.timeout = timeout

    def run(
        self,
        sources: Sequence[ScrapingSource],
        *,
        start_page: int = 1,
        end_page: Optional[int] = None,
    ) -> List[CrawlerResult]:
        results: List[CrawlerResult] = []
        for source in sources:
            scraper_cls = get_scraper_for(source)
            if not scraper_cls:
                print(f"[skip] 등록된 스크래퍼가 없어 건너뜀: {source.slug} ({source.name})")
                continue
            scraper = scraper_cls(session=self.session, delay=self.delay, timeout=self.timeout)
            page_limit = end_page or source.max_pages
            if page_limit < start_page:
                page_limit = start_page
            articles = scraper.collect(source, start_page=start_page, end_page=page_limit)
            results.append(CrawlerResult(source=source, articles=articles))
        return results


__all__ = ["Crawler", "CrawlerResult"]
