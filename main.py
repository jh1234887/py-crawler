from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import List, Sequence

from .config import (
    CrawlerConfig,
    DEFAULT_CONFIG_PATH,
    HwpxSource,
    RssSource,
    ScrapingSource,
)
from .core import Crawler
from .hwpx import get_hwpx_collector
from .hwpx.base import HwpxDocument
from .rss import RssArticle, RssCollector


@dataclass
class HwpxResult:
    source: HwpxSource
    documents: List[HwpxDocument]

    def to_dict(self) -> dict:
        return {
            "source": self.source.slug,
            "name": self.source.name,
            "documents": [
                {
                    "title": doc.title,
                    "pageUrl": doc.page_url,
                    "previewUrls": doc.preview_urls,
                    **({"content": doc.content} if doc.content else {}),
                    **({"meta": doc.meta} if doc.meta else {}),
                }
                for doc in self.documents
            ],
        }


@dataclass
class RssResult:
    source: RssSource
    articles: List[RssArticle]

    def to_dict(self) -> dict:
        return {
            "source": self.source.slug,
            "name": self.source.name,
            "articles": [article.to_dict() for article in self.articles],
        }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Selector-based news crawler")
    parser.add_argument(
        "--mode",
        choices=("scrape", "hwpx", "rss"),
        default="scrape",
        help="실행 모드를 선택합니다 (기본: scrape)",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help="경로를 지정하지 않으면 extended_config.json을 사용합니다.",
    )
    parser.add_argument(
        "--source",
        "-s",
        action="append",
        dest="sources",
        help="수집할 소스를 슬러그 또는 이름으로 지정합니다. 여러 번 사용할 수 있습니다.",
    )
    parser.add_argument(
        "--start-page",
        type=int,
        default=1,
        help="시작 페이지 (기본값: 1)",
    )
    parser.add_argument(
        "--end-page",
        type=int,
        help="마지막 페이지 (포함). 지정하지 않으면 설정 파일에 정의된 값 또는 1 사용.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="시작 페이지부터 처리할 페이지 수",  # overrides end-page when provided
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="결과를 JSON 파일로 저장합니다.",
    )
    parser.add_argument(
        "--list-sources",
        action="store_true",
        help="사용 가능한 소스 목록을 출력하고 종료합니다.",
    )
    parser.add_argument(
        "--no-content",
        action="store_true",
        help="HWPX 모드에서 텍스트 추출을 생략합니다.",
    )
    parser.add_argument(
        "--headless",
        dest="headless",
        action="store_true",
        help="HWPX 모드에서 브라우저를 헤드리스로 실행합니다 (기본).",
    )
    parser.add_argument(
        "--no-headless",
        dest="headless",
        action="store_false",
        help="HWPX 모드에서 브라우저 창을 표시합니다.",
    )
    parser.set_defaults(headless=None)
    return parser


def resolve_sources(config: CrawlerConfig, tokens: Sequence[str] | None) -> List[ScrapingSource]:
    enabled = list(config.enabled_sources())
    if not tokens:
        return enabled

    resolved: List[ScrapingSource] = []
    token_list: List[str] = []
    for token in tokens:
        token_list.extend([seg.strip() for seg in token.split(",") if seg.strip()])

    if any(token.lower() == "all" for token in token_list):
        return enabled

    for token in token_list:
        source = config.find_by_slug(token) or config.find_by_name(token)
        if not source:
            raise SystemExit(f"알 수 없는 소스: {token}")
        if not source.enabled:
            raise SystemExit(f"비활성화된 소스입니다: {source.slug}")
        resolved.append(source)

    # Preserve original order without duplicates.
    ordered: List[ScrapingSource] = []
    seen = set()
    for source in config.sources:
        if source in resolved and source.slug not in seen:
            ordered.append(source)
            seen.add(source.slug)
    return ordered


def resolve_hwpx_sources(config: CrawlerConfig, tokens: Sequence[str] | None) -> List[HwpxSource]:
    enabled = list(config.enabled_hwpx_sources())
    if not tokens:
        return enabled

    resolved: List[HwpxSource] = []
    token_list: List[str] = []
    for token in tokens:
        token_list.extend([seg.strip() for seg in token.split(",") if seg.strip()])

    if any(token.lower() == "all" for token in token_list):
        return enabled

    for token in token_list:
        source = config.find_hwpx(token)
        if not source:
            raise SystemExit(f"알 수 없는 HWPX 소스: {token}")
        if not source.enabled:
            raise SystemExit(f"비활성화된 HWPX 소스입니다: {source.slug}")
        resolved.append(source)

    ordered: List[HwpxSource] = []
    seen = set()
    for source in config.hwpx_sources:
        if source in resolved and source.slug not in seen:
            ordered.append(source)
            seen.add(source.slug)
    return ordered


def resolve_rss_sources(config: CrawlerConfig, tokens: Sequence[str] | None) -> List[RssSource]:
    enabled = list(config.enabled_rss_sources())
    if not tokens:
        return enabled

    resolved: List[RssSource] = []
    token_list: List[str] = []
    for token in tokens:
        token_list.extend([seg.strip() for seg in token.split(",") if seg.strip()])

    if any(token.lower() == "all" for token in token_list):
        return enabled

    for token in token_list:
        source = config.find_rss(token)
        if not source:
            raise SystemExit(f"알 수 없는 RSS 소스: {token}")
        if not source.enabled:
            raise SystemExit(f"비활성화된 RSS 소스입니다: {source.slug}")
        resolved.append(source)

    ordered: List[RssSource] = []
    seen = set()
    for source in config.rss_sources:
        if source in resolved and source.slug not in seen:
            ordered.append(source)
            seen.add(source.slug)
    return ordered


def output_summary(results) -> None:
    for result in results:
        print(f"[{result.source.slug}] {result.source.name}: {len(result.articles)}건 수집")


def output_json(results, path: Path) -> None:
    payload = [result.to_dict() for result in results]
    write_json(payload, path)


def output_hwpx_summary(results: List[HwpxResult]) -> None:
    for result in results:
        print(f"[{result.source.slug}] {result.source.name}: {len(result.documents)}건 수집")


def output_hwpx_json(results: List[HwpxResult], path: Path) -> None:
    payload = [result.to_dict() for result in results]
    write_json(payload, path)


def output_rss_summary(results: List[RssResult]) -> None:
    for result in results:
        print(f"[{result.source.slug}] {result.source.name}: {len(result.articles)}건 수집")


def output_rss_json(results: List[RssResult], path: Path) -> None:
    payload = [result.to_dict() for result in results]
    write_json(payload, path)


def write_json(payload, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    config = CrawlerConfig.from_file(args.config)

    if args.list_sources:
        if args.mode == "scrape":
            if not config.sources:
                print("등록된 scrape 소스가 없습니다.")
            else:
                for source in config.sources:
                    status = "활성" if source.enabled else "비활성"
                    print(f"{source.slug:12s} | {source.name} | {status}")
        elif args.mode == "hwpx":
            if not config.hwpx_sources:
                print("등록된 HWPX 소스가 없습니다.")
            else:
                for source in config.hwpx_sources:
                    status = "활성" if source.enabled else "비활성"
                    print(f"{source.slug:12s} | {source.name} | {status}")
        elif args.mode == "rss":
            if not config.rss_sources:
                print("등록된 RSS 소스가 없습니다.")
            else:
                for source in config.rss_sources:
                    status = "활성" if source.enabled else "비활성"
                    print(f"{source.slug:12s} | {source.name} | {status}")
        return 0

    if args.mode == "scrape":
        sources = resolve_sources(config, args.sources)
        if not sources:
            print("활성화된 소스가 없습니다.")
            return 1

        start_page = max(1, args.start_page)
        end_page = args.end_page
        if args.limit is not None:
            end_page = start_page + max(0, args.limit - 1)

        crawler = Crawler(config)
        results = crawler.run(sources, start_page=start_page, end_page=end_page)

        if args.output:
            output_json(results, args.output)
            print(f"JSON 결과를 {args.output} 위치에 저장했습니다.")
        else:
            output_summary(results)
        return 0

    if args.mode == "hwpx":
        sources = resolve_hwpx_sources(config, args.sources)
        if not sources:
            print("활성화된 HWPX 소스가 없습니다.")
            return 1

        start_page = max(1, args.start_page)
        limit_end = None
        if args.limit is not None:
            limit_end = start_page + max(0, args.limit - 1)

        headless = True if args.headless is None else bool(args.headless)
        fetch_content = not args.no_content

        results: List[HwpxResult] = []
        for source in sources:
            collector_cls = get_hwpx_collector(source)
            if not collector_cls:
                print(f"[skip] 등록된 HWPX 수집기가 없어 건너뜀: {source.slug} ({source.name})")
                continue
            collector = collector_cls(headless=headless)

            page_limit: int | None = None
            if args.end_page is not None:
                page_limit = args.end_page
            elif source.raw.get("pagenum") is not None:
                page_limit = source.max_pages

            if limit_end is not None:
                page_limit = min(limit_end, page_limit) if page_limit is not None else limit_end

            if page_limit is not None and page_limit < start_page:
                page_limit = start_page

            documents = collector.collect(
                source,
                start_page=start_page,
                end_page=page_limit,
                fetch_content=fetch_content,
            )
            results.append(HwpxResult(source=source, documents=documents))

        if args.output:
            output_hwpx_json(results, args.output)
            print(f"JSON 결과를 {args.output} 위치에 저장했습니다.")
        else:
            output_hwpx_summary(results)
        return 0

    if args.mode == "rss":
        sources = resolve_rss_sources(config, args.sources)
        if not sources:
            print("활성화된 RSS 소스가 없습니다.")
            return 1

        collector = RssCollector()
        results: List[RssResult] = []
        for source in sources:
            articles = collector.collect(source)
            if args.limit is not None:
                articles = articles[: args.limit]
            results.append(RssResult(source=source, articles=articles))

        if args.output:
            output_rss_json(results, args.output)
            print(f"JSON 결과를 {args.output} 위치에 저장했습니다.")
        else:
            output_rss_summary(results)
        return 0

    raise SystemExit("지원하지 않는 모드입니다.")


if __name__ == "__main__":
    raise SystemExit(main())
