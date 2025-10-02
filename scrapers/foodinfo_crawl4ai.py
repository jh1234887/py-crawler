from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from bs4 import BeautifulSoup

try:  # pragma: no cover - optional dependencies
    from crawl4ai import AsyncWebCrawler
except ImportError:  # pragma: no cover
    AsyncWebCrawler = None  # type: ignore[misc]

try:  # pragma: no cover - optional dependency
    from playwright.async_api import TimeoutError as PlaywrightTimeoutError
    from playwright.async_api import async_playwright
except ImportError:  # pragma: no cover
    PlaywrightTimeoutError = Exception  # type: ignore[assignment]
    async_playwright = None  # type: ignore[assignment]


LIST_URL = (
    "https://www.foodinfo.or.kr/portal/bbs/selectBoardList.do?"
    "bbsId=10000000000000000500&goMenuNo=9000001102&topMenuNo=9000001080&upperMenuNo=9000001101"
)

CONTENT_SELECTORS = [
    ".bbs_view_contents",
    ".board_view_content",
    ".view_content",
    ".view_area",
    ".view_wrap",
    ".bbs_content",
    ".board_content",
    "#content",
    "[class*='view'] [class*='content']",
]


async def get_detail_content_async(url: str, list_url: str) -> Optional[str]:
    if async_playwright is None:  # pragma: no cover - playwright optional
        return None

    async with async_playwright() as playwright:  # type: ignore[union-attr]
        browser = await playwright.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-gpu",
            ],
        )
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/123.0.0.0 Safari/537.36"
            ),
            locale="ko-KR",
            timezone_id="Asia/Seoul",
        )
        page = await context.new_page()
        try:
            await page.goto(list_url, wait_until="domcontentloaded")
            await page.wait_for_load_state("networkidle")

            await page.goto(url, referer=list_url, wait_until="domcontentloaded")
            await page.wait_for_load_state("networkidle")

            for selector in CONTENT_SELECTORS:
                try:
                    element = await page.wait_for_selector(selector, timeout=4000, state="attached")
                except PlaywrightTimeoutError:
                    continue
                text = (await element.text_content()) or ""
                if text.strip():
                    return text.strip()

            for frame in page.frames:
                if frame == page.main_frame:
                    continue
                for selector in CONTENT_SELECTORS:
                    try:
                        element = await frame.wait_for_selector(selector, timeout=3000, state="attached")
                    except PlaywrightTimeoutError:
                        continue
                    text = (await element.text_content()) or ""
                    if text.strip():
                        return text.strip()

            try:
                mobile_url = url.replace("https://www.foodinfo.or.kr", "https://m.foodinfo.or.kr")
                await page.goto(mobile_url, referer=list_url, wait_until="domcontentloaded")
                await page.wait_for_load_state("networkidle")
                for selector in CONTENT_SELECTORS:
                    try:
                        element = await page.wait_for_selector(selector, timeout=3000, state="attached")
                    except PlaywrightTimeoutError:
                        continue
                    text = (await element.text_content()) or ""
                    if text.strip():
                        return text.strip()
            except Exception:
                pass

            html = await page.content()
            soup = BeautifulSoup(html, "html.parser")
            body = soup.find("body")
            if body:
                for unwanted in body(["script", "style", "nav", "header", "footer", "aside"]):
                    unwanted.decompose()
                text = " ".join(body.get_text("\n").split())
                return text[:5000] if text else None
            return None
        finally:
            await context.close()
            await browser.close()


def _default_log(*args: Any, **kwargs: Any) -> None:
    print(*args, **kwargs)


class FoodInfoCrawler:
    def __init__(
        self,
        *,
        list_url: str = LIST_URL,
        detail_limit: int = 5,
        verbose: bool = False,
    ) -> None:
        self.list_url = list_url or LIST_URL
        self.base_url = "https://www.foodinfo.or.kr"
        self.detail_limit = max(detail_limit, 0)
        self.verbose = verbose
        self._log = _default_log if verbose else (lambda *args, **kwargs: None)

    async def crawl_press_releases(self) -> List[Dict[str, Any]]:
        if AsyncWebCrawler is None:  # pragma: no cover
            raise RuntimeError("crawl4ai 패키지를 찾을 수 없습니다.")

        async with AsyncWebCrawler(verbose=self.verbose) as crawler:  # type: ignore[call-arg]
            self._log("보도자료 목록 페이지를 크롤링합니다...")

            list_result = await crawler.arun(
                url=self.list_url,
                wait_for="table, .board_list, .list_table",
                delay=5,
                js_code="""
                await new Promise(resolve => setTimeout(resolve, 3000));

                const clickableElements = document.querySelectorAll('[onclick]');
                clickableElements.forEach((elem, index) => {
                    const onclick = elem.getAttribute('onclick');
                    elem.setAttribute('data-original-onclick', onclick);
                    elem.setAttribute('data-element-index', index);
                });
                """,
            )

            if not getattr(list_result, "success", False):
                self._log("목록 페이지 크롤링 실패")
                return []

            soup = BeautifulSoup(list_result.html, "html.parser")
            tables = soup.find_all("table")
            self._log(f"테이블 개수: {len(tables)}")

            press_releases: List[Dict[str, Any]] = []
            for table in tables:
                rows = table.find_all("tr")
                for row in rows:
                    cells = row.find_all(["td"])
                    if len(cells) >= 4:
                        try:
                            number_text = cells[0].get_text(strip=True)
                            if not number_text.isdigit():
                                continue
                            number = int(number_text)

                            title_cell = cells[1]
                            onclick_elem = title_cell.find(attrs={"onclick": True})

                            detail_url: Optional[str] = None
                            if onclick_elem:
                                print(cells)
                                title = onclick_elem.get_text(strip=True)
                                detail_url = self.extract_detail_url(onclick_elem.get("onclick", ""))
                                # date = cells[-2].get_text(strip=True)
                                # views_text = cells[-1].get_text(strip=True)
                            else:
                                link = title_cell.find("a")
                                
                                if link:
                                    title = link.get_text(strip=True)
                                    href = link.get("href", "")
                                    if href and href != "#none":
                                        detail_url = href if href.startswith("http") else self.base_url + href
                                    else:
                                        detail_url = None
                                else:
                                    title = title_cell.get_text(strip=True)

                            date = cells[-2].get_text(strip=True)
                            views_text = cells[-1].get_text(strip=True)
                            views = int(views_text.replace(",", "")) if views_text.replace(",", "").isdigit() else 0

                            press_releases.append(
                                {
                                    "number": number,
                                    "title": title,
                                    "date": date,
                                    "views": views,
                                    "detail_url": detail_url,
                                    "content": None,
                                }
                            )
                            print(press_releases)
                        except Exception as exc:
                            self._log(f"행 파싱 중 오류: {exc}")
                            continue

            self._log(f"원본 기준 총 {len(press_releases)}건 수집")

            uniq: Dict[int, Dict[str, Any]] = {}
            for release in press_releases:
                if release["number"] not in uniq:
                    uniq[release["number"]] = release
            press_releases = list(uniq.values())
            press_releases.sort(key=lambda item: item["number"], reverse=True)
            self._log(f"중복 제거 후 {len(press_releases)}건")

            limit = self.detail_limit or 0
            slice_limit = press_releases[:limit] if limit else []

            for index, release in enumerate(slice_limit, start=1):
                if not release.get("detail_url"):
                    self._log(f"[상세 URL 없음] {release['title']}")
                    continue

                self._log(f"[{index}/{len(slice_limit)}] 상세 크롤링: {release['title']}")
                try:
                    detail_result = await crawler.arun(
                        url=release["detail_url"],
                        wait_for="div, .content, .board",
                        delay=3,
                        js_code="""
                            await new Promise(resolve => setTimeout(resolve, 2000));
                        """,
                    )

                    content: Optional[str] = None
                    if getattr(detail_result, "success", False):
                        detail_soup = BeautifulSoup(detail_result.html, "html.parser")
                        for selector in CONTENT_SELECTORS:
                            elem = detail_soup.select_one(selector)
                            if elem:
                                content = elem.get_text(strip=True)
                                break

                    if not content:
                        self._log("선택자 매칭 실패 → Playwright 폴백 시도")
                        try:
                            content = await get_detail_content_async(release["detail_url"], self.list_url)
                            if content:
                                self._log(f"본문 길이: {len(content)}")
                        except Exception as exc:
                            self._log(f"Playwright 폴백 중 오류: {exc}")

                    release["content"] = content
                except Exception as exc:
                    self._log(f"상세 페이지 크롤링 오류: {exc}")

                await asyncio.sleep(2)

            return press_releases

    def extract_detail_url(self, onclick_value: str) -> Optional[str]:
        if not onclick_value:
            return None
        try:
            main_pattern = (
                r"main\s*\(\s*['\"]V['\"]?\s*,\s*['\"](\d+)['\"]?\s*(?:,\s*['\"]([^'\"]*)['\"])?"
            )
            match = re.search(main_pattern, onclick_value)
            if match:
                ntt_id = match.group(1)
                bbs_id = match.group(2) if match.group(2) else "10000000000000000500"
                return (
                    f"{self.base_url}/portal/bbs/detailBBSArticle.do?nttId={ntt_id}&bbsId={bbs_id}"
                )

            patterns = [
                r"selectBboardDetail\s*\(\s*['\"]([^'\"]*)['\"](?:\s*,\s*['\"]([^'\"]*)['\"])?",
                r"fnSelectBboardDetail\s*\(\s*['\"]([^'\"]*)['\"](?:\s*,\s*['\"]([^'\"]*)['\"])?",
                r"goView\s*\(\s*['\"]([^'\"]*)['\"](?:\s*,\s*['\"]([^'\"]*)['\"])?",
                r"[a-zA-Z_]\w*\s*\(\s*['\"]([^'\"]*)['\"](?:\s*,\s*['\"]([^'\"]*)['\"])?",
            ]
            for pattern in patterns:
                match = re.search(pattern, onclick_value)
                if match:
                    params = [p for p in match.groups() if p is not None]
                    if params:
                        ntt_id = params[0]
                        bbs_id = params[1] if len(params) > 1 else "10000000000000000500"
                        return (
                            f"{self.base_url}/portal/bbs/selectBboardDetail.do"
                            f"?nttId={ntt_id}&bbsId={bbs_id}"
                        )

            numbers = re.findall(r"\d+", onclick_value)
            if numbers:
                ntt_id = numbers[0]
                bbs_id = "10000000000000000500"
                return (
                    f"{self.base_url}/portal/bbs/selectBboardDetail.do?nttId={ntt_id}&bbsId={bbs_id}"
                )
        except Exception as exc:
            self._log(f"URL 추출 중 오류: {exc}")

        return None

    def save_to_json(self, press_releases: List[Dict[str, Any]], filename: str = "press_releases.json") -> None:
        with open(filename, "w", encoding="utf-8") as file:
            json.dump(press_releases, file, ensure_ascii=False, indent=2)
        self._log(f"결과가 {filename}에 저장되었습니다.")

    def print_summary(self, press_releases: List[Dict[str, Any]]) -> None:
        self._log("\n=== 크롤링 결과 요약 ===")
        self._log(f"총 {len(press_releases)}개의 보도자료")
        self._log("\n상위 5개 보도자료:")
        for release in press_releases:
            self._log(f"\n번호: {release.get('number')}")
            self._log(f"제목: {release.get('title')}")
            self._log(f"날짜: {release.get('date')}")
            self._log(f"조회수: {release.get('views')}")
            self._log(f"상세 URL: {release.get('detail_url')}")
            content = release.get("content")
            if content:
                preview = content[:200] + "..." if len(content) > 200 else content
                self._log(f"내용 미리보기: {preview}")
            self._log("-" * 50)

    def run(self) -> List[Dict[str, Any]]:
        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            return loop.run_until_complete(self.crawl_press_releases())
        finally:
            asyncio.set_event_loop(None)
            loop.close()


__all__ = [
    "FoodInfoCrawler",
    "get_detail_content_async",
    "LIST_URL",
    "CONTENT_SELECTORS",
]

