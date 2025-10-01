from __future__ import annotations

from bs4 import BeautifulSoup, Tag

TARGET_REMOVALS = ["script", "style", ".ad", ".advertisement"]


def clean_article_node(node: Tag | None) -> str:
    if node is None:
        return ""
    for selector in TARGET_REMOVALS:
        for unwanted in node.select(selector):
            unwanted.decompose()
    return node.get_text(separator="\n", strip=True)


def ensure_absolute(url: str, base_url: str) -> str:
    if url.startswith("http"):
        return url
    if url.startswith("//"):
        scheme = base_url.split(":", 1)[0]
        return f"{scheme}:{url}"
    if url.startswith("/"):
        if base_url.endswith("/"):
            return base_url.rstrip("/") + url
        return base_url + url
    if base_url.endswith("/"):
        return base_url + url
    return base_url + "/" + url


__all__ = ["clean_article_node", "ensure_absolute"]
