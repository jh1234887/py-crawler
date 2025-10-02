from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence

import requests
import urllib3
from bs4 import BeautifulSoup
from dateutil import parser as date_parser
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig
from crawl4ai.content_filter_strategy import PruningContentFilter
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator

from ..config import CollectionSettings, CrawlerConfig, NaverApiConfig, NaverCategory

# Crawl4AI relies on Playwright under the hood; suppress noisy TLS warnings when verify=False.
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

LOGGER = logging.getLogger("crawler.naver")

DEFAULT_CRAWL4AI_CONFIG: Dict[str, object] = {
    "browser_type": "chromium",
    "headless": True,
    "text_mode": True,
    "enable_stealth": False,
    "verbose_browser": False,
    "prune_threshold": 0.48,
    "prune_threshold_type": "dynamic",
    "min_word_threshold": 5,
    "word_count_threshold": 80,
    "timeout_sec": 40,
    "retries": 2,
    "delay_between": 0.2,
    "verbose_run": False,
}


@dataclass
class NaverArticle:
    keyword: str
    title: str
    link: str
    description: str
    pub_date: Optional[str]
    iso_date: Optional[str]
    category: str
    body_markdown_fit: Optional[str] = None
    body_markdown_raw: Optional[str] = None
    raw: Dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, object]:
        payload: Dict[str, object] = {
            "keyword": self.keyword,
            "title": self.title,
            "link": self.link,
            "description": self.description,
            "category": self.category,
        }
        if self.pub_date:
            payload["pubDate"] = self.pub_date
        if self.iso_date:
            payload["isoDate"] = self.iso_date
        if self.body_markdown_fit:
            payload["bodyMarkdownFit"] = self.body_markdown_fit
        if self.body_markdown_raw:
            payload["bodyMarkdownRaw"] = self.body_markdown_raw
        if self.raw:
            payload["raw"] = self.raw
        return payload


@dataclass
class NaverResult:
    category: NaverCategory
    articles: List[NaverArticle]

    def to_dict(self) -> Dict[str, object]:
        return {
            "category": self.category.slug,
            "name": self.category.display_name,
            "count": len(self.articles),
            "articles": [article.to_dict() for article in self.articles],
        }


class NaverCollector:
    def __init__(
        self,
        config: CrawlerConfig,
        *,
        session: Optional[requests.Session] = None,
    ) -> None:
        self.config = config
        self.session = session or requests.Session()
        # Some endpoints still serve legacy certificates.
        self.session.verify = False

        self.collection_settings = config.collection_settings
        self.naver_api_config = config.naver_api
        self.crawl4ai_config = {**DEFAULT_CRAWL4AI_CONFIG, **config.crawl4ai}

        self.categories = [category for category in config.enabled_naver_categories()]
        self.stats = {
            "startedAt": datetime.now().isoformat(),
            "naverApiCalls": 0,
            "totalArticles": 0,
        }

        self._client_id, self._client_secret = self._resolve_credentials(self.naver_api_config)
        self.headers = {
            "X-Naver-Client-Id": self._client_id or "",
            "X-Naver-Client-Secret": self._client_secret or "",
            "User-Agent": "Mozilla/5.0 (compatible; crawler/1.0)",
        }

        self._browser_config = BrowserConfig(
            browser_type=str(self.crawl4ai_config.get("browser_type", "chromium")),
            headless=bool(self.crawl4ai_config.get("headless", True)),
            text_mode=bool(self.crawl4ai_config.get("text_mode", True)),
            enable_stealth=bool(self.crawl4ai_config.get("enable_stealth", False)),
            verbose=bool(self.crawl4ai_config.get("verbose_browser", False)),
        )
        prune_filter = PruningContentFilter(
            threshold=float(self.crawl4ai_config.get("prune_threshold", 0.48)),
            threshold_type=str(self.crawl4ai_config.get("prune_threshold_type", "dynamic")),
            min_word_threshold=int(self.crawl4ai_config.get("min_word_threshold", 5)),
        )
        markdown_generator = DefaultMarkdownGenerator(content_filter=prune_filter)
        self._run_config = CrawlerRunConfig(
            markdown_generator=markdown_generator,
            word_count_threshold=int(self.crawl4ai_config.get("word_count_threshold", 80)),
            verbose=bool(self.crawl4ai_config.get("verbose_run", False)),
        )
        self.crawl_timeout = float(self.crawl4ai_config.get("timeout_sec", 40))
        self.crawl_retries = int(self.crawl4ai_config.get("retries", 2))
        self.crawl_delay = float(self.crawl4ai_config.get("delay_between", 0.2))

    @staticmethod
    def _resolve_credentials(api_config: NaverApiConfig) -> tuple[Optional[str], Optional[str]]:
        client_id = api_config.client_id
        client_secret = api_config.client_secret
        if not client_id and api_config.client_id_env:
            client_id = os.getenv(api_config.client_id_env)
        if not client_secret and api_config.client_secret_env:
            client_secret = os.getenv(api_config.client_secret_env)
        return client_id, client_secret

    @property
    def has_credentials(self) -> bool:
        return bool(self._client_id and self._client_secret)

    def _ensure_credentials(self) -> bool:
        if not self.has_credentials:
            LOGGER.error("Naver API credentials are missing. Provide client_id/client_secret or env names in config.")
            return False
        return True

    def _clean_html(self, html_text: str) -> str:
        if not html_text:
            return ""
        soup = BeautifulSoup(html_text, "html.parser")
        text = soup.get_text()
        return (
            text.replace("&lt;", "<")
            .replace("&gt;", ">")
            .replace("&amp;", "&")
            .replace("&quot;", '"')
            .replace("&#039;", "'")
            .replace("&nbsp;", " ")
        ).strip()

    @staticmethod
    def _parse_datetime(value: Optional[str]) -> Optional[str]:
        if not value:
            return None
        try:
            return date_parser.parse(value).isoformat()
        except Exception:
            return None

    def _filter_recent(self, articles: Iterable[NaverArticle]) -> List[NaverArticle]:
        cutoff = datetime.now(timezone.utc) - timedelta(days=self.collection_settings.days_filter)
        filtered: List[NaverArticle] = []
        for article in articles:
            if not article.iso_date:
                filtered.append(article)
                continue
            try:
                parsed = date_parser.isoparse(article.iso_date)
            except (ValueError, TypeError):
                filtered.append(article)
                continue
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            else:
                parsed = parsed.astimezone(timezone.utc)
            if parsed >= cutoff:
                filtered.append(article)
        return filtered

    async def _acrawl_markdown(self, url: str) -> Dict[str, Optional[str]]:
        for attempt in range(self.crawl_retries + 1):
            try:
                async with AsyncWebCrawler(config=self._browser_config) as crawler:
                    async def _run() -> object:
                        return await crawler.arun(url=url, config=self._run_config)

                    result = await asyncio.wait_for(_run(), timeout=self.crawl_timeout)
                    success = getattr(result, "success", True)
                    if not success:
                        LOGGER.warning("Crawl failed (%s): %s", url, getattr(result, "error_message", ""))
                    markdown = getattr(result, "markdown", None)
                    fit_md = getattr(markdown, "fit_markdown", None) if markdown else None
                    raw_md = getattr(markdown, "raw_markdown", None) if markdown else None
                    if fit_md or raw_md:
                        return {"fit": fit_md or raw_md, "raw": raw_md or fit_md}
            except Exception as exc:  # noqa: BLE001
                LOGGER.debug("Crawl exception (%s, attempt %d): %s", url, attempt + 1, exc)
            time.sleep(self.crawl_delay)
        return {"fit": None, "raw": None}

    def _crawl_markdown(self, url: str) -> Dict[str, Optional[str]]:
        try:
            return asyncio.run(self._acrawl_markdown(url))
        except RuntimeError:
            loop = asyncio.new_event_loop()
            try:
                asyncio.set_event_loop(loop)
                return loop.run_until_complete(self._acrawl_markdown(url))
            finally:
                loop.close()

    def collect_keyword(
        self,
        keyword: str,
        category: NaverCategory,
        *,
        display: Optional[int] = None,
    ) -> List[NaverArticle]:
        limit = display or self.collection_settings.naver_api_display
        limit = min(limit, self.collection_settings.max_articles_per_keyword)
        params = {
            "query": keyword,
            "display": limit,
            "start": self.collection_settings.naver_api_start,
            "sort": self.collection_settings.naver_api_sort,
        }

        try:
            resp = self.session.get(
                self.naver_api_config.base_url,
                params=params,
                headers=self.headers,
                timeout=self.collection_settings.request_timeout,
            )
            resp.raise_for_status()
        except requests.exceptions.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else "?"
            LOGGER.error("HTTP error (%s, keyword=%s): %s", status, keyword, exc)
            return []
        except requests.exceptions.RequestException as exc:
            LOGGER.error("Request error (keyword=%s): %s", keyword, exc)
            return []

        self.stats["naverApiCalls"] += 1
        data = resp.json()
        items = data.get("items", [])
        articles: List[NaverArticle] = []
        category_slug = f"naver_{category.slug}"
        for item in items:
            title = self._clean_html(item.get("title", ""))
            description = self._clean_html(item.get("description", ""))
            link = item.get("originallink") or item.get("link") or ""
            pub_date_raw = item.get("pubDate")
            iso_date = self._parse_datetime(pub_date_raw)
            article = NaverArticle(
                keyword=keyword,
                title=title,
                link=link,
                description=description,
                pub_date=pub_date_raw,
                iso_date=iso_date,
                category=category_slug,
                raw={"origin": item},
            )
            if link:
                markdown = self._crawl_markdown(link)
                article.body_markdown_fit = markdown.get("fit")
                article.body_markdown_raw = markdown.get("raw")
            articles.append(article)
            if self.crawl_delay:
                time.sleep(self.crawl_delay)

        time.sleep(self.collection_settings.naver_api_delay)
        return self._filter_recent(articles)

    def collect_category(
        self,
        category: NaverCategory,
        *,
        display: Optional[int] = None,
    ) -> NaverResult:
        aggregated: List[NaverArticle] = []
        for keyword in category.keywords:
            aggregated.extend(self.collect_keyword(keyword, category, display=display))
        filtered = self._filter_recent(aggregated)
        self.stats["totalArticles"] += len(filtered)
        return NaverResult(category=category, articles=filtered)

    def collect(
        self,
        categories: Sequence[NaverCategory] | None = None,
        *,
        display: Optional[int] = None,
    ) -> List[NaverResult]:
        if not self._ensure_credentials():
            return []
        active_categories = list(categories) if categories else self.categories
        results: List[NaverResult] = []
        for category in active_categories:
            if not category.keywords:
                LOGGER.debug("Skip category without keywords: %s", category.slug)
                continue
            LOGGER.info("Collecting Naver news | category=%s", category.slug)
            result = self.collect_category(category, display=display)
            results.append(result)
        return results

    def to_payload(self, results: Sequence[NaverResult]) -> Dict[str, object]:
        category_payload = {
            result.category.slug: len(result.articles) for result in results
        }
        total_articles = sum(category_payload.values())
        return {
            "meta": {
                "timestamp": datetime.now().isoformat(),
                "totalArticles": total_articles,
                "categories": category_payload,
                "stats": self.stats,
                "collectionSettings": self.collection_settings.raw,
                "naverApi": self.naver_api_config.raw,
            },
            "articles": {
                f"naver_{result.category.slug}": [article.to_dict() for article in result.articles]
                for result in results
            },
        }

    def save_json(self, results: Sequence[NaverResult], path: Path) -> Path:
        payload = self.to_payload(results)
        path = path.resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        LOGGER.info("Saved Naver output to %s", path)
        return path


__all__ = ["NaverCollector", "NaverResult", "NaverArticle"]
