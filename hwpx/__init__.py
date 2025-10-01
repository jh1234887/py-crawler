from __future__ import annotations

from typing import Dict, Optional, Type

from ..config import HwpxSource
from .base import BaseHwpxCollector
from .kca import KcaHwpxCollector
from .mfds import MfdsHwpxCollector

HWPX_REGISTRY: Dict[str, Type[BaseHwpxCollector]] = {
    "한국소비자원": KcaHwpxCollector,
    "kca": KcaHwpxCollector,
    "식약처": MfdsHwpxCollector,
    "mfds": MfdsHwpxCollector,
}


def get_hwpx_collector(source: HwpxSource) -> Optional[Type[BaseHwpxCollector]]:
    slug = source.slug.lower()
    if slug in HWPX_REGISTRY:
        return HWPX_REGISTRY[slug]
    name = source.name.strip().lower()
    return HWPX_REGISTRY.get(name)


__all__ = ["HWPX_REGISTRY", "get_hwpx_collector"]
