from __future__ import annotations

import asyncio
from typing import Iterable, List, Sequence, TYPE_CHECKING

from extract_hwpx_latest import WebTextExtractor

if TYPE_CHECKING:
    from .base import HwpxDocument


class HwpxExtractionSession:
    def __init__(self, *, headless: bool = True, clean_text: bool = True) -> None:
        self._extractor = WebTextExtractor()
        self._headless = headless
        self._clean_text = clean_text

    async def __aenter__(self) -> "HwpxExtractionSession":
        await self._extractor.start_browser(headless=self._headless)
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self._extractor.close_browser()

    async def extract(self, url: str) -> str:
        return await self._extractor.extract_text_from_url(url, clean_text=self._clean_text)


async def extract_many_async(
    urls: Iterable[str],
    *,
    headless: bool = True,
    clean_text: bool = True,
) -> List[str]:
    async with HwpxExtractionSession(headless=headless, clean_text=clean_text) as session:
        results: List[str] = []
        for url in urls:
            text = await session.extract(url)
            results.append(text)
        return results


def extract_many(
    urls: Iterable[str],
    *,
    headless: bool = True,
    clean_text: bool = True,
) -> List[str]:
    return asyncio.run(extract_many_async(urls, headless=headless, clean_text=clean_text))


async def _populate_documents_async(
    documents: Sequence["HwpxDocument"],
    *,
    headless: bool = True,
    clean_text: bool = True,
) -> None:
    async with HwpxExtractionSession(headless=headless, clean_text=clean_text) as session:
        for document in documents:
            if not document.preview_urls:
                continue
            last_text: str | None = None
            for url in document.preview_urls:
                text = await session.extract(url)
                if text:
                    last_text = text
            if last_text:
                document.content = last_text


def populate_document_contents(
    documents: Sequence["HwpxDocument"],
    *,
    headless: bool = True,
    clean_text: bool = True,
) -> None:
    if not documents:
        return
    asyncio.run(_populate_documents_async(documents, headless=headless, clean_text=clean_text))


__all__ = [
    "HwpxExtractionSession",
    "extract_many",
    "extract_many_async",
    "populate_document_contents",
]
