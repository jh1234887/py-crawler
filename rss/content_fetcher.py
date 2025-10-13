from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Callable, Dict, Optional

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


Extractor = Callable[[BeautifulSoup], Optional[str]]


def _normalize_node_text(node: BeautifulSoup) -> str:
    text = node.get_text(separator="\n")
    return ArticleContentFetcher._normalize_text(text)


def _extract_food_safety_recall(soup: BeautifulSoup) -> Optional[str]:
    container = soup.select_one("div.inner-body") or soup.select_one("div.board_view")
    target_root = container or soup
    dl_nodes = target_root.find_all("dl")
    parts = []
    if dl_nodes:
        nodes = dl_nodes
    else:
        nodes = [target_root]
    for dl_node in nodes:
        text = _normalize_node_text(dl_node)
        if text:
            parts.append(text)
    combined = "\n\n".join(parts).strip()
    return combined or None


def _extract_food_safety_administrative(soup: BeautifulSoup) -> Optional[str]:
    target = soup.select_one("div.inner-body") or soup.select_one("div.board_view")
    if not target:
        return None
    text = _normalize_node_text(target)
    return text or None


def _extract_kfdn_article(soup: BeautifulSoup) -> Optional[str]:
    container = soup.select_one("td.td_sub_read_contents")
    if not container:
        return None
    parts = []
    subtitle = container.select_one("span.read_subtitle")
    if subtitle:
        parts.append(_normalize_node_text(subtitle))
    body = container.select_one("div#textinput")
    if body:
        parts.append(_normalize_node_text(body))
    if not parts:
        return None
    combined = "\n\n".join(part for part in parts if part)
    return combined or None


CUSTOM_EXTRACTORS: Dict[str, Extractor] = {
    "foodsafety_suspension": _extract_food_safety_recall,
    "foodsafety_administ": _extract_food_safety_administrative,
    "kfdn": _extract_kfdn_article,
}


@dataclass
class ArticleContentFetcher:
    session: requests.Session
    timeout: int = 30
    max_retries: int = 2
    retry_delay: float = 1.0
    delay: float = 0.0

    def fetch(self, url: str, *, encoding: Optional[str] = None, source_slug: Optional[str] = None) -> Optional[str]:
        attempts = self.max_retries + 1
        for attempt in range(1, attempts + 1):
            try:
                response = self.session.get(url, headers=DEFAULT_HEADERS, timeout=self.timeout)
                response.raise_for_status()
                if encoding:
                    response.encoding = encoding
                html = response.text
                content = self.extract_content(html, source_slug=source_slug)
                if self.delay:
                    time.sleep(self.delay)
                return content
            except Exception as exc:
                print(f"[rss] \ubcf8\ubb38 \uc694\uccad \uc2e4\ud328 ({url}): {exc}")
                if attempt < attempts:
                    time.sleep(self.retry_delay)
        return None

    def extract_content(self, html: str, *, source_slug: Optional[str] = None) -> Optional[str]:
        soup = BeautifulSoup(html, "html.parser")
        if source_slug:
            extractor = CUSTOM_EXTRACTORS.get(source_slug)
            if extractor:
                custom_text = extractor(soup)
                if custom_text:
                    return custom_text

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
