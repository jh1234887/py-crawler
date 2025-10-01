from __future__ import annotations

from typing import List
from urllib import request

import feedparser

from ..config import HwpxSource
from .base import BaseHwpxCollector, HwpxDocument
from .extractor import populate_document_contents
from .preview import collect_preview_urls

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0 Safari/537.36"
    )
}


class MfdsHwpxCollector(BaseHwpxCollector):
    """식품의약품안전처(RSS) 문서 뷰어에서 텍스트 추출."""

    def collect(
        self,
        source: HwpxSource,
        *,
        start_page: int,
        end_page: int | None,
        fetch_content: bool = True,
    ) -> List[HwpxDocument]:
        # 페이지 매김이 없는 RSS이므로 start/end는 개수 제한으로 해석
        entries = self._load_feed(source)
        if not entries:
            return []

        subset = entries[start_page - 1 : end_page] if end_page else entries[start_page - 1 :]
        documents: List[HwpxDocument] = []

        for index, entry in enumerate(subset, start=start_page):
            link = getattr(entry, "link", None)
            title = getattr(entry, "title", None)
            if not link or not title:
                continue

            preview_urls = collect_preview_urls(link)
            if not preview_urls:
                continue

            documents.append(
                HwpxDocument(
                    title=title,
                    page_url=link,
                    preview_urls=preview_urls,
                    meta={
                        "index": index,
                        "published": getattr(entry, "published", None),
                        "summary": getattr(entry, "summary", None),
                    },
                )
            )
            self.sleep()

        if fetch_content:
            try:
                populate_document_contents(documents, headless=self.headless)
            except Exception as exc:
                print(f"[hwpx:mfds] 텍스트 추출 중 오류: {exc}")

        return documents

    def _load_feed(self, source: HwpxSource):
        req = request.Request(source.url, headers=DEFAULT_HEADERS)
        if source.encoding:
            req.add_header("Accept-Charset", source.encoding)
        try:
            with request.urlopen(req) as resp:
                feed = feedparser.parse(resp)
        except Exception as exc:
            print(f"[hwpx:mfds] RSS 요청 실패 ({source.url}): {exc}")
            return []

        if getattr(feed, "bozo", False):
            print(f"[hwpx:mfds] RSS 파싱 오류: {getattr(feed, 'bozo_exception', '')}")
            return []

        return feed.entries
