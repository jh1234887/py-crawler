import json
from datetime import datetime
from email.utils import parsedate_to_datetime
from pathlib import Path

import psycopg2
from psycopg2.extras import Json

JSON_PATH = Path("data/251002_naver.json")


def parse_iso_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def parse_rfc2822(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None


def load_payload(path: Path) -> dict:
    with path.open(encoding="utf-8") as fp:
        return json.load(fp)


def main() -> None:
    payload = load_payload(JSON_PATH)
    meta = payload.get("meta", {})
    articles = payload.get("articles", {})

    conn = psycopg2.connect(
        host="172.17.0.3",
        port=5432,
        user="jihye",
        password="1q2w3e4r!@#",
        dbname="original_data_db",
    )
    conn.autocommit = False

    try:
        with conn, conn.cursor() as cur:
            run_id = insert_meta(cur, meta)
            insert_articles(cur, run_id, articles)
    finally:
        conn.close()


def insert_meta(cur, meta: dict) -> int:
    sql = """
        INSERT INTO naver_collection_meta (
            collected_at,
            total_articles,
            categories,
            collection_stats,
            config_used
        ) VALUES (%(collected_at)s, %(total_articles)s, %(categories)s,
                  %(collection_stats)s, %(config_used)s)
        RETURNING run_id;
    """

    params = {
        "collected_at": parse_iso_dt(meta.get("timestamp")),
        "total_articles": meta.get("total_articles", 0),
        "categories": Json(meta.get("categories", {})),
        "collection_stats": Json(meta.get("collection_stats", {})),
        "config_used": Json(meta.get("config_used", {})),
    }

    cur.execute(sql, params)
    run_id = cur.fetchone()[0]
    return run_id


def insert_articles(cur, run_id: int, articles: dict) -> None:
    sql = """
        INSERT INTO naver_article (
            run_id,
            category,
            keyword,
            source,
            title,
            content_title,
            link,
            originallink,
            description,
            content_text,
            content_byline,
            pub_date,
            iso_date,
            content_datetime,
            collection_time,
            raw_payload
        ) VALUES (
            %(run_id)s,
            %(category)s,
            %(keyword)s,
            %(source)s,
            %(title)s,
            %(content_title)s,
            %(link)s,
            %(originallink)s,
            %(description)s,
            %(content_text)s,
            %(content_byline)s,
            %(pub_date)s,
            %(iso_date)s,
            %(content_datetime)s,
            %(collection_time)s,
            %(raw_payload)s
        )
        ON CONFLICT (link) DO NOTHING;
    """

    for category, rows in articles.items():
        for row in rows or []:
            params = {
                "run_id": run_id,
                "category": category,
                "keyword": row.get("keyword"),
                "source": row.get("source"),
                "title": row.get("title"),
                "content_title": row.get("content_title"),
                "link": row.get("link"),
                "originallink": row.get("originallink"),
                "description": row.get("description"),
                "content_text": row.get("content_text"),
                "content_byline": row.get("content_byline"),
                "pub_date": parse_rfc2822(row.get("pub_date")),
                "iso_date": parse_iso_dt(row.get("iso_date")),
                "content_datetime": parse_iso_dt(row.get("content_datetime")),
                "collection_time": parse_iso_dt(row.get("collection_time")),
                "raw_payload": Json(row),
            }
            cur.execute(sql, params)


if __name__ == "__main__":
    main()
