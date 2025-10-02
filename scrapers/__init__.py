from __future__ import annotations

from typing import Dict, Optional, Type

from ..config import ScrapingSource
from .base import BaseScraper

SCRAPER_REGISTRY: Dict[str, Type[BaseScraper]] = {}


def register_scraper(*slugs: str):
    def decorator(cls: Type[BaseScraper]) -> Type[BaseScraper]:
        for slug in slugs:
            SCRAPER_REGISTRY[slug.lower()] = cls
        return cls

    return decorator


def get_scraper_for(source: ScrapingSource) -> Optional[Type[BaseScraper]]:
    return SCRAPER_REGISTRY.get(source.slug.lower())


__all__ = ["SCRAPER_REGISTRY", "register_scraper", "get_scraper_for"]

# Ensure scrapers are registered on import.
from . import consumernews, cucs, foodinfo, foodnews, foodtoday, medipana, nutradex  # noqa: E402 F401
