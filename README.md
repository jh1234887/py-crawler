# Crawler

스크래핑·추출 흐름을 모듈화한 패키지입니다. 웹 HTML 스크래핑(`scrape`), HWPX 문서 추출(`hwpx`), RSS 수집(`rss`) 3가지 모드를 지원하며 모두 `argparse` 기반 CLI로 제어합니다.  

## 폴더 구조

```
crawler/
├── __init__.py          # 모듈 진입점 (`python -m crawler.main`)
├── README.md            # 현재 문서
├── config.py            # scraping/rss/hwpx 공통 설정 로더
├── core.py              # HTML 스크래퍼 오케스트레이터
├── main.py              # CLI 파서 및 모드별 실행 분기
├── utils.py             # 콘텐츠 정제, URL 보정 헬퍼
├── hwpx/                # HWPX 문서 미리보기 파싱 및 텍스트 추출
│   ├── __init__.py      # 사이트별 수집기 레지스트리
│   ├── base.py          # 공통 데이터 클래스와 수집기 기본형
│   ├── extractor.py     # Playwright 기반 텍스트 추출 세션
│   ├── kca.py           # 한국소비자원 게시판 수집기
│   └── parsers.py       # iframe/synapviewer 링크 파서
├── rss/                 # RSS 피드 수집기
│   ├── __init__.py
│   └── base.py          # feedparser 래퍼와 RssArticle 정의
└── scrapers/            # HTML 기반 뉴스 스크래퍼
    ├── __init__.py
    ├── base.py
    ├── consumernews.py
    ├── cucs.py
    ├── foodnews.py
    ├── foodtoday.py
    ├── medipana.py
    └── nutradex.py
```

설정 파일은 기본적으로 루트의 `extended_config.json`을 사용하지만, `config.json` 같은 다른 JSON을 `--config` 옵션으로 지정할 수 있습니다. 각 섹션(`scraping_sources`, `hwpx_sources`, `rss_sources`)의 `slug` 또는 `name`을 CLI에서 그대로 지정하면 됩니다.

## 실행 방법

> ⚠️ 실제 뉴스 사이트 및 문서 뷰어에 요청을 전송하므로 실행 전 네트워크 정책과 대상 사이트 약관을 반드시 확인하세요.

### 공통 옵션

```bash
python -m crawler.main [--mode MODE] [--source ...] [--output PATH]
```

- `--mode`: `scrape`(기본) · `hwpx` · `rss` 중 선택
- `--source` / `-s`: 특정 소스를 슬러그 또는 이름으로 지정 (여러 번 사용하거나 `,`로 구분 가능, `all` 지원)
- `--limit`: `scrape`/`hwpx` 모드에서는 시작 페이지 기준 처리 페이지 수, `rss` 모드에서는 기사 개수 제한
- `--output`: 결과를 JSON 파일로 저장 (지정하지 않으면 콘솔 요약만 출력)
- `--list-sources`: 현재 모드에 해당하는 소스 목록과 활성화 여부 출력 후 종료

### scrape (HTML 스크래핑)

```bash
# 식품저널만 2페이지까지 스크래핑
python -m crawler.main --mode scrape --source foodnews --limit 2

# 여러 소스를 동시에 실행
python -m crawler.main -s foodnews -s medipana

# 결과를 JSON으로 저장
python -m crawler.main --mode scrape --output data/scrape.json
```

### hwpx (HWPX 문서 추출)

Playwright 기반 브라우저를 사용하므로 최초 1회 `playwright install chromium` 실행이 필요합니다.

```bash
# 한국소비자원 게시판에서 HWPX 문서를 추출 (텍스트 포함)
python -m crawler.main --mode hwpx --source "한국소비자원"

# 브라우저 창을 띄워서 디버깅
python -m crawler.main --mode hwpx --source kca --no-headless

# 미리보기 URL만 수집하고 텍스트 추출은 생략
python -m crawler.main --mode hwpx --no-content
```

현재 수집기는 `한국소비자원`(게시판)과 `식약처`(RSS → 문서뷰어) 구조를 지원합니다. 추가 기관을 연결하려면 `crawler/hwpx/`에 새 클래스를 작성하고 `HWPX_REGISTRY`에 매핑하세요.
슬러그는 설정 파일(`hwpx_sources`)의 `slug` 필드를 따르며, 지정하지 않으면 이름(예: `식약처`)으로도 접근할 수 있습니다.

### rss (RSS 피드)

```bash
# 기본 활성 RSS 모두 수집
python -m crawler.main --mode rss

# 특정 피드만 5개 기사씩 확인
python -m crawler.main --mode rss --source "식품음료신문" --limit 5
```

## 확장 및 커스터마이징

- HTML 스크래퍼: `scrapers/`에 클래스를 추가하고 `@register_scraper("slug")`로 등록합니다.
- HWPX: `hwpx/` 하위에 수집기 클래스를 구현하고 `HWPX_REGISTRY`에 매핑합니다. 필요 시 `extractor.py`의 세션 래퍼를 재사용하여 텍스트 추출을 통합하세요.
- RSS: 추가적인 전처리가 필요하면 `rss/base.py`의 `RssCollector`를 확장하거나 새로운 파서를 작성합니다.
- 공통 설정 필드는 `crawler/config.py`에서 데이터 클래스로 관리되므로, 추가 필드가 필요하면 `raw` 딕셔너리를 참조하거나 데이터 클래스를 확장하면 됩니다.
