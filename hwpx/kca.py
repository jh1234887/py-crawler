from __future__ import annotations

from typing import List
from urllib.parse import urlparse
from bs4 import BeautifulSoup
import re
from crawl4ai import AsyncWebCrawler
import asyncio
import requests
from urllib.parse import urljoin
from ..config import HwpxSource
from .base import BaseHwpxCollector, HwpxDocument
from .extractor import populate_document_contents
from .preview import collect_preview_urls

IFRAME_KEY = "docviewer/skin/doc.html"  # 미리보기 iframe 식별 키

def _extract_urls_from_iframes(soup, base):
    """이미 열려 있는 프리뷰 iframe의 src 추출 (가장 확실/간단)"""
    urls = set()
    for iframe in soup.select("div.bbs_file_preview iframe[src]"):
        src = iframe.get("src")
        if src and IFRAME_KEY in src:
            urls.add(urljoin(base, src))
    return urls

def _find_any_rs_suffix(soup):
    """
    같은 페이지 내 다른 iframe에서 rs 파라미터만 떼어 재사용.
    예: /docviewer/result/ntc0021/49374/1/202509
    """
    any_iframe = soup.select_one(f"div.bbs_file_preview iframe[src*='docviewer/result/']")
    if not any_iframe or not any_iframe.get("src"):
        return None
    m = re.search(r"[?&]rs=([^&]+)", any_iframe["src"])
    return m.group(1) if m else None

def _extract_urls_from_onclick(soup, base):
    """
    onclick="fnConvertDocViewer('brd_id','seq','file_seq')" + 파일명으로
    미리보기 URL 조립. rs는 같은 페이지 iframe에서 재사용.
    """
    urls = set()
    onclick_re = re.compile(r"fnConvertDocViewer\('([^']+)','([^']+)','([^']+)'\)")
    rs_suffix = _find_any_rs_suffix(soup)

    for a in soup.select("a.bbs_icon_preveiw[onclick]"):
        m = onclick_re.search(a.get("onclick", ""))
        if not m:
            continue
        brd_id, seq, file_seq = m.groups()

        li = a.find_parent("li")
        strong = li.select_one(".bbs_file_cont > strong") if li else None
        filename = strong.get_text(strip=True) if strong else None

        if not filename:
            continue

        # rs 추정/조립
        rs = None
        # 1) 같은 li에 프리뷰 iframe이 있으면 그걸 우선 신뢰
        if li:
            ifr = li.select_one("div.bbs_file_preview iframe[src]")
            if ifr and ifr.get("src"):
                m2 = re.search(r"[?&]rs=([^&]+)", ifr["src"])
                if m2:
                    rs = m2.group(1)

        # 2) 페이지 내 임의 iframe의 연월(YYYYMM)만 재사용
        if not rs and rs_suffix:
            # rs_suffix 예: /docviewer/result/ntc0021/49374/1/202509
            tail = rs_suffix.strip("/").split("/")
            yyyy_mm = tail[-1] if tail else ""
            rs = f"/docviewer/result/{brd_id}/{seq}/{file_seq}/{yyyy_mm}"

        if rs:
            url = f"/docviewer/skin/doc.html?fn={filename}&rs={rs}"
            urls.add(urljoin(base, url))

    return urls
def _extract_synapviewer_urls(soup, base, page_url):
    """
    바로보기(synapviewer) 링크 추출
    """
    urls = set()
    synapviewer_re = re.compile(r"window\.open\('(synapviewer\.do[^']+)'\)")
    
    # 페이지 URL에서 경로 추출 (예: /home/)
    from urllib.parse import urlparse
    parsed = urlparse(page_url)
    page_path = parsed.path.rsplit('/', 1)[0] + '/'  # 마지막 파일명 제거
    
    for div in soup.select("div[id^='fileDiv']"):
        links = div.select("a")
        for link in links:
            onclick = link.get("onclick", "")
            m = synapviewer_re.search(onclick)
            if m:
                viewer_url = m.group(1)
                # 상대 경로면 페이지 경로와 결합
                if not viewer_url.startswith(('http://', 'https://', '/')):
                    viewer_url = page_path + viewer_url
                urls.add(urljoin(base, viewer_url))
    
    return urls

# 또는 특정 fileDiv3만 추출하려면:
def _extract_filediv3_synapviewer_url(soup, base):
    """
    fileDiv3의 바로보기 링크만 추출
    """
    synapviewer_re = re.compile(r"window\.open\('(synapviewer\.do[^']+)'\)")
    
    div3 = soup.select_one("#fileDiv3")
    if not div3:
        return None
    
    for link in div3.select("a"):
        onclick = link.get("onclick", "")
        m = synapviewer_re.search(onclick)
        if m:
            return urljoin(base, m.group(1))
    
    return None
async def extract_preview_urls(page_url: str, base_url: str = None):
    """
    주어진 게시글 URL에서 미리보기 URL들(set)을 추출.
    """
    if base_url is None:
        from urllib.parse import urlparse
        p = urlparse(page_url)
        base_url = f"{p.scheme}://{p.netloc}"

    async with AsyncWebCrawler() as crawler:
        r = await crawler.arun(page_url)
        html = r.html

    soup = BeautifulSoup(html, "html.parser")

    urls = set()
    urls |= _extract_urls_from_iframes(soup, base_url)
    urls |= _extract_synapviewer_urls(soup, base_url, page_url)  # page_url 전달
    
    return list(urls)


async def extract_preview_urls(page_url: str, base_url: str = None):
    """
    주어진 게시글 URL에서 미리보기 URL들(set)을 추출.
    """
    if base_url is None:
        from urllib.parse import urlparse
        p = urlparse(page_url)
        base_url = f"{p.scheme}://{p.netloc}"

    async with AsyncWebCrawler() as crawler:
        r = await crawler.arun(page_url)
        html = r.html

    soup = BeautifulSoup(html, "html.parser")

    urls = set()
    urls |= _extract_urls_from_iframes(soup, base_url)
    urls |= _extract_synapviewer_urls(soup, base_url, page_url)  # page_url 전달
    
    return list(urls)

class KcaHwpxCollector(BaseHwpxCollector):
    """한국소비자원 게시판에서 HWPX 문서를 추출합니다."""

    def collect(
        self,
        source: HwpxSource,
        *,
        start_page: int,
        end_page: int | None,
        fetch_content: bool = True,
    ) -> List[HwpxDocument]:
        documents: List[HwpxDocument] = []
        page_limit = end_page if end_page is not None else source.max_pages
        if page_limit < start_page:
            page_limit = start_page
        parsed = urlparse(source.url)
        base_url = f"{parsed.scheme}://{parsed.netloc}"

        for page_num in range(start_page, page_limit + 1):
            list_url = source.url.format(page_num) if "{}" in source.url else source.url
            try:
                soup = self.fetch(list_url)
            except requests.RequestException as exc:
                print(f"[hwpx:kca] 페이지 요청 실패 ({list_url}): {exc}")
                continue

            rows = soup.select("table.board tbody tr")
            if not rows:
                break

            for index, row in enumerate(rows, start=1):
                link_element = row.select_one("td.title a")
                if not link_element or "href" not in link_element.attrs:
                    continue

                if not link_element:
                    continue
                
                relative_url = link_element['href']
                
                # 상대 URL 처리
                if relative_url.startswith('?'):
                    full_url = base_url + "/home/sub.do" + relative_url
                elif relative_url.startswith('/'):
                    full_url = base_url + relative_url
                else:
                    full_url = base_url + '/' + relative_url

                title = link_element.get_text(strip=True)
                href = link_element["href"]
                page_url = self.ensure_absolute(href, base_url)
                # preview_urls = collect_preview_urls(page_url)
                urls = asyncio.get_event_loop().run_until_complete(extract_preview_urls(full_url))
                for u in sorted(urls):
                    print(u)
                documents.append(
                    HwpxDocument(
                        title=title,
                        page_url=page_url,
                        preview_urls=[urls[-1]],
                        meta={"page": page_num, "index": index},
                    )
                )
                self.sleep()

            self.sleep()

        if fetch_content:
            try:
                populate_document_contents(documents, headless=self.headless)
            except Exception as exc:
                print(f"[hwpx:kca] 텍스트 추출 중 오류: {exc}")

        return documents
