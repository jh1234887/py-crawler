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
class CrawlerConfig:
    sources: List[ScrapingSource]
    rss_sources: List["RssSource"]
    hwpx_sources: List["HwpxSource"]

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
        return cls(sources=sources, rss_sources=rss_sources, hwpx_sources=hwpx_sources)

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
    "DEFAULT_CONFIG_PATH",
]
