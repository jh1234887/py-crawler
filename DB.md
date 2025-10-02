# 데이터베이스 설계 및 적재 요약

## 테이블 구조
- `naver_collection_meta`
  - 수집 실행(run) 단위 메타데이터 저장.
  - 주요 컬럼: `run_id`(PK), `collected_at`, `total_articles`, `categories`, `collection_stats`, `config_used`.
  - JSON 필드는 그대로 `jsonb` 로 보존하여 추후 진단 및 감사 용도로 활용.

- `naver_article`
  - 기사 단위 데이터 저장.
  - 주요 컬럼: `article_id`(PK), `run_id`(FK), `category`, `keyword`, `source`, `title`, `link`, `originallink`, `description`, `content_text`, `content_byline`, `pub_date`, `iso_date`, `content_datetime`, `collection_time`, `raw_payload`.
  - `run_id` 는 `naver_collection_meta` 와 외래키로 연결되어 있으며, `raw_payload` 에는 원본 JSON 문서를 `jsonb` 로 그대로 저장.

## 중복 방지 전략
- 같은 키워드로 동일 기사 URL 이 반복 수집되는 것을 막기 위해 `naver_article(link)` 에 유니크 인덱스를 생성하고 `INSERT ... ON CONFLICT (link) DO NOTHING` 적용.
- 2025-10-02 데이터(`data/251002_naver.json`) 의 경우 원본 기사 390 건 중 링크 중복이 59 건 존재하여, 테이블에는 고유 링크 331 건만 적재됨.
- 중복 여부는 Python 스크립트 또는 SQL 에서 `COUNT(DISTINCT link)` 로 확인 가능.

## 적재 흐름
1. `psql` 로 접속 후 아래 DDL 실행.
   ```sql
   CREATE TABLE naver_collection_meta (
       run_id           bigserial PRIMARY KEY,
       collected_at     timestamptz NOT NULL,
       total_articles   integer      NOT NULL,
       categories       jsonb        NOT NULL,
       collection_stats jsonb        NOT NULL,
       config_used      jsonb        NOT NULL
   );

   CREATE TABLE naver_article (
       article_id        bigserial PRIMARY KEY,
       run_id            bigint      NOT NULL REFERENCES naver_collection_meta(run_id) ON DELETE CASCADE,
       category          text        NOT NULL,
       keyword           text,
       source            text,
       title             text        NOT NULL,
       content_title     text,
       link              text        NOT NULL,
       originallink      text,
       description       text,
       content_text      text,
       content_byline    text,
       pub_date          timestamptz,
       iso_date          timestamptz,
       content_datetime  timestamp,
       collection_time   timestamptz,
       raw_payload       jsonb
   );

   CREATE UNIQUE INDEX naver_article_link_uidx ON naver_article (link);
   CREATE INDEX naver_article_category_idx ON naver_article (category);
   CREATE INDEX naver_article_iso_date_idx ON naver_article (iso_date DESC);
   ```

2. `python py-crawler/postgres_db.py` 실행.
   - 스크립트가 메타 정보를 먼저 `naver_collection_meta` 에 저장하여 `run_id` 를 확보.
   - 이어서 각 기사 레코드를 파싱해 `naver_article` 에 적재.
   - 날짜 문자열은 ISO, RFC 2822 형식 모두 안전하게 파싱하고, 원본 레코드는 `raw_payload` 로 보관.

3. 적재 검증 예시.
   ```sql
   SELECT run_id, collected_at, total_articles
     FROM naver_collection_meta
     ORDER BY run_id DESC LIMIT 1;

   SELECT run_id, COUNT(*)
     FROM naver_article GROUP BY run_id;

   SELECT category, COUNT(*)
   FROM naver_article
   WHERE run_id = (SELECT MAX(run_id) FROM naver_article)
   GROUP BY category;
   ```
   - `total_articles` 는 390 으로 JSON 원본과 일치하지만, `naver_article` 는 중복 제거 후 331 건이 조회됨.

4. 터미널에서 한글 출력이 필요하면 `psql` 실행 시 `
   \encoding UTF8` 또는 `PGCLIENTENCODING=UTF8 psql ...` 로 세션 인코딩을 맞춘 뒤 `SELECT` 결과를 확인.

## Python 검증 스니펫
- `psql` 대신 Python 으로 상위 기사 제목을 확인할 때는 다음 스크립트가 사용됨.
  ```python
  import json
  from email.utils import parsedate_to_datetime

  with open("data/251002_naver.json", encoding="utf-8") as fp:
      data = json.load(fp)["articles"]

  rows = [row for items in data.values() for row in items]
  for row in sorted(rows,
                    key=lambda r: parsedate_to_datetime(r["pub_date"]),
                    reverse=True)[:5]:
      print(row["pub_date"], row["title"])
  ```

위 과정을 통해 `naver_collection_meta` 와 `naver_article` 이 일관되게 유지되며, 링크 중복이 있을 경우 자동으로 필터링된다는 점을 확인했다.
