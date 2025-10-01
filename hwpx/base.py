from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import requests
from bs4 import BeautifulSoup

from ..config import HwpxSource
from ..utils import ensure_absolute


@dataclass
class HwpxDocument:
    title: str
    page_url: str
    preview_urls: str
    content: Optional[str] = None
    meta: Dict[str, Any] = field(default_factory=dict)


class BaseHwpxCollector(ABC):
    def __init__(
        self,
        *,
        session: Optional[requests.Session] = None,
        delay: float = 0.5,
        timeout: int = 15,
        headless: bool = True,
    ) -> None:
        self.session = session or requests.Session()
        self.delay = delay
        self.timeout = timeout
        self.headless = headless

    def fetch(self, url: str) -> BeautifulSoup:
        response = self.session.get(url, timeout=self.timeout)
        response.raise_for_status()
        response.encoding = response.encoding or "utf-8"
        return BeautifulSoup(response.text, "html.parser")

    def sleep(self) -> None:
        if self.delay:
            time.sleep(self.delay)

    def ensure_absolute(self, url: str, base_url: str) -> str:
        return ensure_absolute(url, base_url)

    @abstractmethod
    def collect(
        self,
        source: HwpxSource,
        *,
        start_page: int,
        end_page: int | None,
        fetch_content: bool = True,
    ) -> List[HwpxDocument]:
        raise NotImplementedError


__all__ = ["HwpxDocument", "BaseHwpxCollector"]
