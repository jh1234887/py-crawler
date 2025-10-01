"""
웹페이지 텍스트 추출기 - Playwright 사용
식품의약품안전처 문서뷰어와 같은 iframe 포함 페이지에서 텍스트 추출
"""

import asyncio
from playwright.async_api import async_playwright
import re
from typing import Optional

class WebTextExtractor:
    def __init__(self):
        self.browser = None
        self.page = None
        self.playwright = None

    async def start_browser(self, headless: bool = True):
        """브라우저 시작"""
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=headless)
        self.page = await self.browser.new_page()
        
        # 타임아웃 설정
        self.page.set_default_timeout(30000)  # 30초

    async def close_browser(self):
        """브라우저 종료"""
        if self.page:
            await self.page.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

    async def extract_text_from_url(self, url: str, clean_text: bool = True) -> str:
        try:
            print(f"페이지 로딩 중: {url}")
            await self.page.goto(url, wait_until="domcontentloaded")

            # 주요 iframe가 동적 로드될 시간을 조금 준다
            try:
                await self.page.wait_for_load_state('networkidle', timeout=15000)
            except Exception:
                pass  # 네트워크가 계속 열려 있어도 넘어감

            text = await self._extract_text_with_iframe()

            if clean_text:
                text = self._clean_text(text)

            return text
        except Exception as e:
            print(f"텍스트 추출 중 오류 발생: {e}")
            return ""

    async def _extract_text_with_iframe(self) -> str:
        """
        페이지 및 (동일 출처인) 모든 iframe까지 포함해서 텍스트 추출.
        - #innerWrap을 우선적으로 기다림
        - 모든 frame을 순회하며 body.innerText 수집
        - 각 frame에서 스크롤을 끝까지 내려 지연 로딩 대응
        """
        collected = []
        async def _scroll_and_get_text(frame):
            # 지연 로딩/가상뷰어 대응: 천천히 끝까지 스크롤하며 텍스트 수집
            try:
                return await frame.evaluate(
                    """async () => {
                        const sleep = (ms) => new Promise(r => setTimeout(r, ms));
                        let lastY = -1, sameCount = 0;
                        for (let i = 0; i < 50; i++) {
                            window.scrollBy(0, Math.max(200, window.innerHeight));
                            await sleep(120);
                            // 더 이상 스크롤이 내려가지 않으면 중단
                            if (window.scrollY === lastY) {
                                sameCount++;
                                if (sameCount >= 3) break;
                            } else {
                                sameCount = 0;
                                lastY = window.scrollY;
                            }
                        }
                        return document.body ? document.body.innerText : "";
                    }"""
                )
            except Exception:
                # 보수적 fallback
                try:
                    return await frame.locator("body").inner_text()
                except Exception:
                    return ""

        try:
            # 우선 특정 iframe(#innerWrap)을 기다려 본다(없어도 통과)
            try:
                elem = await self.page.wait_for_selector("iframe#innerWrap", timeout=5000)
                content_frame = await elem.content_frame()
                if content_frame:
                    text = await _scroll_and_get_text(content_frame)
                    if text:
                        collected.append(text.strip())
            except Exception:
                pass  # 없거나 접근 불가해도 계속 진행

            # 페이지의 모든 프레임(상위+하위)을 순회
            for frame in self.page.frames:
                try:
                    text = await _scroll_and_get_text(frame)
                    if text:
                        collected.append(text.strip())
                except Exception:
                    continue

            # 중복 제거 및 합치기
            uniq = []
            seen = set()
            for chunk in collected:
                key = (len(chunk), hash(chunk))
                if key not in seen and chunk:
                    seen.add(key)
                    uniq.append(chunk)

            merged = "\n\n".join(uniq)
            if merged.strip():
                return merged

            # 모든 프레임 접근이 안 되거나 내용이 없으면 body fallback
            return await self.page.inner_text('body')

        except Exception as e:
            print(f"iframe 포함 텍스트 추출 실패, 일반 텍스트로 fallback: {e}")
            try:
                return await self.page.inner_text('body')
            except Exception:
                return ""


    def _clean_text(self, text: str) -> str:
        """텍스트 정리"""
        if not text:
            return ""
        
        # 여러 개의 연속된 공백을 하나로 변경
        text = re.sub(r'\s+', ' ', text)
        
        # 여러 개의 연속된 줄바꿈을 최대 2개로 제한
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        # 앞뒤 공백 제거
        text = text.strip()
        
        return text

    async def save_to_file(self, text: str, filename: str):
        """텍스트를 파일로 저장"""
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(text)
            print(f"텍스트가 {filename}에 저장되었습니다.")
        except Exception as e:
            print(f"파일 저장 중 오류 발생: {e}")

    async def extract_and_save(self, url: str, filename: Optional[str] = None, clean_text: bool = True):
        """URL에서 텍스트를 추출하고 파일로 저장하는 통합 함수"""
        if filename is None:
            # URL에서 파일명 생성
            import urllib.parse
            parsed_url = urllib.parse.urlparse(url)
            filename = f"extracted_text_{parsed_url.netloc.replace('.', '_')}.txt"
        
        text = await self.extract_text_from_url(url, clean_text)
        
        if text:
            await self.save_to_file(text, filename)
            print(f"추출된 텍스트 길이: {len(text)}자")
            return text
        else:
            print("텍스트 추출에 실패했습니다.")
            return ""


async def main():
    """메인 실행 함수"""
    # EXAMPLE
    # 식품의약품안전처 문서 URL
    url = "https://www.mfds.go.kr/docviewer/skin/doc.html?fn=20250929092120147.hwpx&rs=/docviewer/result/ntc0021/49374/1/202509"
    
    # 텍스트 추출기 생성
    extractor = WebTextExtractor()
    
    try:
        # 브라우저 시작
        await extractor.start_browser(headless=True)  # headless=False로 하면 브라우저가 보입니다
        
        # 텍스트 추출 및 저장
        text = await extractor.extract_and_save(
            url=url,
            filename="mfds_press_release.txt",
            clean_text=True
        )
        
        # 결과 출력 (처음 500자만)
        if text:
            print("\n=== 추출된 텍스트 미리보기 ===")
            print(text[:500] + "..." if len(text) > 500 else text)
            
    finally:
        # 브라우저 종료
        await extractor.close_browser()


def simple_extract(url: str, output_file: str = None):
    """간단한 사용을 위한 동기 래퍼 함수"""
    async def _extract():
        extractor = WebTextExtractor()
        try:
            await extractor.start_browser()
            return await extractor.extract_and_save(url, output_file)
        finally:
            await extractor.close_browser()
    
    return asyncio.run(_extract())


if __name__ == "__main__":
    # 실행 방법 1: 비동기 실행
    asyncio.run(main())
    
    # 실행 방법 2: 간단한 함수 사용 (주석 해제하여 사용)
    # url = "https://www.mfds.go.kr/docviewer/skin/doc.html?fn=20250929092120147.hwpx&rs=/docviewer/result/ntc0021/49374/1/202509"
    # simple_extract(url, "extracted_text.txt")