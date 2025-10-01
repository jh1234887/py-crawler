from __future__ import annotations

import re
from typing import Iterable, List, Set
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

IFRAME_KEY = "docviewer/skin/doc.html"


def extract_preview_urls(soup: BeautifulSoup, base_url: str, page_url: str | None = None) -> List[str]:
    urls: Set[str] = set()
    urls |= _extract_urls_from_iframes(soup, base_url)
    urls |= set(_extract_urls_from_onclick(soup, base_url))
    urls |= set(_extract_synapviewer_urls(soup, base_url, page_url or ""))
    return normalize_preview_urls(urls)


def _extract_urls_from_iframes(soup: BeautifulSoup, base: str) -> Set[str]:
    urls: Set[str] = set()
    for iframe in soup.select("div.bbs_file_preview iframe[src]"):
        src = iframe.get("src")
        if src and IFRAME_KEY in src:
            urls.add(urljoin(base, src))
    return urls


def _find_any_rs_suffix(soup: BeautifulSoup) -> str | None:
    any_iframe = soup.select_one("div.bbs_file_preview iframe[src*='docviewer/result/']")
    if not any_iframe or not any_iframe.get("src"):
        return None
    m = re.search(r"[?&]rs=([^&]+)", any_iframe["src"])
    return m.group(1) if m else None


def _extract_urls_from_onclick(soup: BeautifulSoup, base: str) -> List[str]:
    urls: Set[str] = set()
    onclick_re = re.compile(r"fnConvertDocViewer\('([^']+)','([^']+)','([^']+)'\)")
    rs_suffix = _find_any_rs_suffix(soup)

    for anchor in soup.select("a.bbs_icon_preveiw[onclick]"):
        m = onclick_re.search(anchor.get("onclick", ""))
        if not m:
            continue
        brd_id, seq, file_seq = m.groups()
        li = anchor.find_parent("li")
        filename = None
        if li:
            strong = li.select_one(".bbs_file_cont > strong")
            if strong:
                filename = strong.get_text(strip=True)
        if not filename:
            continue

        rs = None
        if li:
            iframe = li.select_one("div.bbs_file_preview iframe[src]")
            if iframe and iframe.get("src"):
                m2 = re.search(r"[?&]rs=([^&]+)", iframe["src"])
                if m2:
                    rs = m2.group(1)

        if not rs and rs_suffix:
            tail = rs_suffix.strip("/").split("/")
            yyyy_mm = tail[-1] if tail else ""
            rs = f"/docviewer/result/{brd_id}/{seq}/{file_seq}/{yyyy_mm}"

        if rs:
            url = f"/docviewer/skin/doc.html?fn={filename}&rs={rs}"
            urls.add(urljoin(base, url))

    return list(urls)


def _extract_synapviewer_urls(soup: BeautifulSoup, base: str, page_url: str) -> Set[str]:
    urls: Set[str] = set()
    synapviewer_re = re.compile(r"window\.open\('(synapviewer\.do[^']+)'\)")

    parsed = urlparse(page_url)
    page_path = parsed.path.rsplit('/', 1)[0] + '/' if parsed.path else ''

    for div in soup.select("div[id^='fileDiv']"):
        for link in div.select("a"):
            onclick = link.get("onclick", "")
            m = synapviewer_re.search(onclick)
            if not m:
                continue
            viewer_url = m.group(1)
            if not viewer_url.startswith(("http://", "https://", "/")):
                viewer_url = page_path + viewer_url
            urls.add(urljoin(base, viewer_url))
    return urls


__all__ = ["extract_preview_urls", "normalize_preview_urls"]


def _contains_hangul(text: str) -> bool:
    return any("\uac00" <= ch <= "\ud7a3" for ch in text)


def normalize_preview_urls(urls: Iterable[str]) -> List[str]:
    normalized: List[str] = []
    for url in sorted(set(urls)):
        if not url:
            continue
        clean = url.strip()
        if not clean.startswith("http"):
            continue
        if "docviewer/skin/doc.html" not in clean:
            continue
        if _contains_hangul(clean):
            continue
        clean = clean.replace(" ", "%20")
        normalized.append(clean)
    if normalized:
        return normalized
    fallback = [url.replace(" ", "%20") for url in sorted(set(urls)) if url]
    return fallback
