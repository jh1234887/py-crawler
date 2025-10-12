from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Optional

import requests
from bs4 import BeautifulSoup

from ..scrapers.base import DEFAULT_HEADERS

EXCLUDED_TAGS = {"script", "style", "noscript", "header", "footer", "nav", "aside", "form", "svg"}
DEFAULT_CANDIDATE_SELECTORS = [
    "article",
    "main",
    "[role='main']",
    ".article",
    ".article-body",
    ".article__body",
    ".article-content",
    ".entry-content",
    ".post-content",
    ".content",
    "#article",
    "#content",
    "#main",
    ".view",
]


@dataclass
class ArticleContentFetcher:
    session: requests.Session
    timeout: int = 30
    max_retries: int = 2
    retry_delay: float = 1.0
    delay: float = 0.0

    def fetch(self, url: str, *, encoding: Optional[str] = None) -> Optional[str]:
        attempts = self.max_retries + 1
        for attempt in range(1, attempts + 1):
            try:
                response = self.session.get(url, headers=DEFAULT_HEADERS, timeout=self.timeout)
                response.raise_for_status()
                if encoding:
                    response.encoding = encoding
                html = response.text
                content = self.extract_content(html)
                if self.delay:
                    time.sleep(self.delay)
                return content
            except Exception as exc:
                print(f"[rss] 본문 요청 실패 ({url}): {exc}")
                if attempt < attempts:
                    time.sleep(self.retry_delay)
        return None

    def extract_content(self, html: str) -> Optional[str]:
        soup = BeautifulSoup(html, "html.parser")
        self._remove_excluded(soup)

        best_text: Optional[str] = None
        best_score = 0

        for selector in DEFAULT_CANDIDATE_SELECTORS:
            for node in soup.select(selector):
                text = self._normalize_text(node.get_text(separator="\n"))
                score = len(text)
                if score > best_score:
                    best_score = score
                    best_text = text

        if best_text:
            return best_text

        paragraph_text = self._combine_paragraphs(soup)
        if paragraph_text:
            return paragraph_text

        body_text = soup.body.get_text(separator="\n") if soup.body else soup.get_text(separator="\n")
        normalized = self._normalize_text(body_text)
        return normalized or None

    def _remove_excluded(self, soup: BeautifulSoup) -> None:
        for tag in EXCLUDED_TAGS:
            for node in soup.find_all(tag):
                node.decompose()

    def _combine_paragraphs(self, soup: BeautifulSoup) -> Optional[str]:
        parts = []
        for node in soup.find_all(["p", "li"]):
            text = self._normalize_text(node.get_text(separator="\n"))
            if text:
                parts.append(text)
        combined = "\n".join(parts).strip()
        return combined or None

    @staticmethod
    def _normalize_text(text: str) -> str:
        if not text:
            return ""
        text = text.replace("\xa0", " ")
        lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]
        lines = [line for line in lines if line]
        return "\n".join(lines).strip()


__all__ = ["ArticleContentFetcher"]
