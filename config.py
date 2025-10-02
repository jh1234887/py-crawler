from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.json"


@dataclass
class ScrapingSource:
    name: str
    url: str
    slug: str
    enabled: bool = True
    raw: Dict[str, Any] = field(default_factory=dict)

    @property
    def max_pages(self) -> int:
        return int(self.raw.get("pagenum", 1))


@dataclass
class CollectionSettings:
    days_filter: int = 7
    naver_api_display: int = 10
    naver_api_start: int = 1
    naver_api_sort: str = "date"
    request_timeout: int = 30
    request_delay: float = 1.0
    retry_attempts: int = 3
    retry_delay: float = 2.0
    naver_api_delay: float = 0.5
    max_articles_per_keyword: int = 10
    raw: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_raw(cls, payload: Dict[str, Any] | None) -> "CollectionSettings":
        payload = payload or {}
        return cls(
            days_filter=int(payload.get("days_filter", 7)),
            naver_api_display=int(payload.get("naver_api_display", 10)),
            naver_api_start=int(payload.get("naver_api_start", 1)),
            naver_api_sort=str(payload.get("naver_api_sort", "date")),
            request_timeout=int(payload.get("request_timeout", 30)),
            request_delay=float(payload.get("request_delay", 1.0)),
            retry_attempts=int(payload.get("retry_attempts", 3)),
            retry_delay=float(payload.get("retry_delay", 2.0)),
            naver_api_delay=float(payload.get("naver_api_delay", 0.5)),
            max_articles_per_keyword=int(payload.get("max_articles_per_keyword", 10)),
            raw=dict(payload),
        )


@dataclass
class NaverApiConfig:
    base_url: str = "https://openapi.naver.com/v1/search/news.json"
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    client_id_env: Optional[str] = None
    client_secret_env: Optional[str] = None
    rate_limit_per_second: Optional[int] = None
    max_daily_calls: Optional[int] = None
    raw: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_raw(cls, payload: Dict[str, Any] | None) -> "NaverApiConfig":
        payload = payload or {}
        return cls(
            base_url=str(payload.get("base_url", cls.base_url)),
            client_id=payload.get("client_id"),
            client_secret=payload.get("client_secret"),
            client_id_env=payload.get("client_id_env"),
            client_secret_env=payload.get("client_secret_env"),
            rate_limit_per_second=payload.get("rate_limit_per_second"),
            max_daily_calls=payload.get("max_daily_calls"),
            raw=dict(payload),
        )


@dataclass
class NaverCategory:
    slug: str
    keywords: List[str]
    enabled: bool = True
    priority: Optional[int] = None
    name: Optional[str] = None
    raw: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_raw(cls, slug: str, payload: Dict[str, Any]) -> "NaverCategory":
        payload = payload or {}
        return cls(
            slug=slug,
            keywords=list(payload.get("keywords", [])),
            enabled=payload.get("enabled", True),
            priority=payload.get("priority"),
            name=payload.get("name") or payload.get("label"),
            raw=dict(payload),
        )

    @property
    def display_name(self) -> str:
        return self.name or self.slug


@dataclass
class CrawlerConfig:
    sources: List[ScrapingSource]
    rss_sources: List["RssSource"]
    hwpx_sources: List["HwpxSource"]
    naver_categories: List[NaverCategory]
    collection_settings: CollectionSettings
    naver_api: NaverApiConfig
    crawl4ai: Dict[str, Any]

    @classmethod
    def from_file(cls, path: Path | str = DEFAULT_CONFIG_PATH) -> "CrawlerConfig":
        config_path = Path(path)
        with config_path.open("r", encoding="utf-8") as fp:
            payload = json.load(fp)
        raw_sources = payload.get("scraping_sources", [])
        sources = [
            ScrapingSource(
                name=entry["name"],
                url=entry["url"],
                slug=entry.get("slug") or entry["name"],
                enabled=entry.get("enabled", True),
                raw=entry,
            )
            for entry in raw_sources
        ]
        rss_sources = [RssSource.from_raw(entry) for entry in payload.get("rss_sources", [])]
        hwpx_sources = [HwpxSource.from_raw(entry) for entry in payload.get("hwpx_sources", [])]
        categories = [
            NaverCategory.from_raw(slug, entry)
            for slug, entry in (payload.get("categories", {}) or {}).items()
        ]
        collection_settings = CollectionSettings.from_raw(payload.get("collection_settings"))
        naver_api = NaverApiConfig.from_raw(payload.get("naver_api"))
        crawl4ai = dict(payload.get("crawl4ai", {}))
        return cls(
            sources=sources,
            rss_sources=rss_sources,
            hwpx_sources=hwpx_sources,
            naver_categories=categories,
            collection_settings=collection_settings,
            naver_api=naver_api,
            crawl4ai=crawl4ai,
        )

    def enabled_sources(self) -> Iterable[ScrapingSource]:
        return (source for source in self.sources if source.enabled)

    def find_by_slug(self, slug: str) -> Optional[ScrapingSource]:
        normalized = slug.lower()
        for source in self.sources:
            if source.slug.lower() == normalized:
                return source
        return None

    def find_by_name(self, name: str) -> Optional[ScrapingSource]:
        normalized = name.strip().lower()
        for source in self.sources:
            if source.name.strip().lower() == normalized:
                return source
        return None

    def enabled_rss_sources(self) -> Iterable["RssSource"]:
        return (source for source in self.rss_sources if source.enabled)

    def enabled_hwpx_sources(self) -> Iterable["HwpxSource"]:
        return (source for source in self.hwpx_sources if source.enabled)

    def find_rss(self, token: str) -> Optional["RssSource"]:
        normalized = token.strip().lower()
        for source in self.rss_sources:
            if source.slug.lower() == normalized or source.name.strip().lower() == normalized:
                return source
        return None

    def find_hwpx(self, token: str) -> Optional["HwpxSource"]:
        normalized = token.strip().lower()
        for source in self.hwpx_sources:
            if source.slug.lower() == normalized or source.name.strip().lower() == normalized:
                return source
        return None

    def enabled_naver_categories(self) -> Iterable[NaverCategory]:
        return (category for category in self.naver_categories if category.enabled and category.keywords)

    def find_naver_category(self, token: str) -> Optional[NaverCategory]:
        normalized = token.strip().lower()
        for category in self.naver_categories:
            if category.slug.lower() == normalized:
                return category
            if category.display_name.lower() == normalized:
                return category
        return None


@dataclass
class RssSource:
    name: str
    url: str
    slug: str
    category: Optional[str] = None
    encoding: Optional[str] = None
    enabled: bool = True
    raw: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_raw(cls, entry: Dict[str, Any]) -> "RssSource":
        return cls(
            name=entry["name"],
            url=entry["url"],
            slug=entry.get("slug") or entry["name"],
            category=entry.get("category"),
            encoding=entry.get("encoding"),
            enabled=entry.get("enabled", True),
            raw=entry,
        )


@dataclass
class HwpxSource:
    name: str
    url: str
    slug: str
    enabled: bool = True
    encoding: Optional[str] = None
    raw: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_raw(cls, entry: Dict[str, Any]) -> "HwpxSource":
        return cls(
            name=entry["name"],
            url=entry["url"],
            slug=entry.get("slug") or entry["name"],
            enabled=entry.get("enabled", True),
            encoding=entry.get("encoding"),
            raw=entry,
        )

    @property
    def max_pages(self) -> int:
        return int(self.raw.get("pagenum", 1))


__all__ = [
    "CrawlerConfig",
    "ScrapingSource",
    "RssSource",
    "HwpxSource",
    "NaverCategory",
    "NaverApiConfig",
    "CollectionSettings",
    "DEFAULT_CONFIG_PATH",
]
