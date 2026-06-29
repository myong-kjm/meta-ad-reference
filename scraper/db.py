"""SQLite 적재 레이어.

광고 한 건을 받아 upsert: 신규면 first_seen_at 기록, 기존이면 last_seen_at만 갱신.
조회 쿼리(어제 신규, 7일 활성) 함수도 여기에.
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "ads.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS competitors (
  page_id TEXT PRIMARY KEY,
  page_name TEXT,
  notes TEXT,
  added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  is_active INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS ads (
  ad_id TEXT PRIMARY KEY,
  page_id TEXT,
  page_name TEXT,
  caption TEXT,
  cta_text TEXT,
  landing_url TEXT,
  display_url TEXT,
  platforms TEXT,
  start_date TEXT,
  active_days INTEGER,
  is_active INTEGER,
  has_video INTEGER,
  media_paths TEXT,
  media_urls TEXT,
  first_seen_at TIMESTAMP,
  last_seen_at TIMESTAMP,
  raw_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_ads_page_id ON ads(page_id);
CREATE INDEX IF NOT EXISTS idx_ads_first_seen ON ads(first_seen_at);
CREATE INDEX IF NOT EXISTS idx_ads_active_days ON ads(active_days);

CREATE TABLE IF NOT EXISTS annotations (
  ad_id TEXT PRIMARY KEY,
  is_winner_candidate INTEGER DEFAULT 0,
  tags TEXT,
  memo TEXT,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS scrape_runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  started_at TIMESTAMP,
  finished_at TIMESTAMP,
  page_id TEXT,
  mode TEXT,
  ads_found INTEGER,
  ads_new INTEGER,
  status TEXT,
  error TEXT
);
"""


def _migrate_media_urls() -> None:
    """raw_json에서 media_urls를 추출해 기존 레코드에 채운다 (최초 1회)."""
    with connect() as conn:
        rows = conn.execute(
            "SELECT ad_id, raw_json FROM ads WHERE media_urls IS NULL AND raw_json IS NOT NULL"
        ).fetchall()
        if not rows:
            return
        updates = []
        for row in rows:
            try:
                raw = json.loads(row["raw_json"])
                snapshot = raw.get("snapshot") or {}
                media_urls: list[dict] = []
                for img in (snapshot.get("images") or []):
                    if isinstance(img, dict):
                        url = (img.get("original_image_url") or img.get("resized_image_url") or img.get("url") or "")
                        if url:
                            media_urls.append({"type": "image", "url": url})
                    elif isinstance(img, str) and img:
                        media_urls.append({"type": "image", "url": img})
                for vid in (snapshot.get("videos") or []):
                    if isinstance(vid, dict):
                        url = vid.get("video_hd_url") or vid.get("video_sd_url") or ""
                        if url:
                            entry: dict = {"type": "video", "url": url}
                            preview = vid.get("video_preview_image_url") or ""
                            if preview:
                                entry["preview"] = preview
                            media_urls.append(entry)
                if media_urls:
                    updates.append((json.dumps(media_urls, ensure_ascii=False), row["ad_id"]))
            except Exception:
                pass
        if updates:
            conn.executemany("UPDATE ads SET media_urls = ? WHERE ad_id = ?", updates)


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with connect() as conn:
        conn.executescript(SCHEMA)
        try:
            conn.execute("ALTER TABLE ads ADD COLUMN media_urls TEXT")
        except Exception:
            pass
    _migrate_media_urls()


@contextmanager
def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def upsert_competitor(page_id: str, page_name: str, notes: str = "") -> None:
    with connect() as conn:
        conn.execute(
            """INSERT INTO competitors (page_id, page_name, notes)
               VALUES (?, ?, ?)
               ON CONFLICT(page_id) DO UPDATE SET
                 page_name = excluded.page_name,
                 notes = excluded.notes""",
            (page_id, page_name, notes),
        )


def set_competitor_name(page_id: str, page_name: str) -> None:
    """경쟁사 표시 이름만 갱신 (notes·is_active·added_at 유지)."""
    with connect() as conn:
        conn.execute(
            "UPDATE competitors SET page_name = ? WHERE page_id = ?",
            (page_name, str(page_id)),
        )


def delete_competitor(page_id: str) -> int:
    """경쟁사 + 관련 광고·어노테이션 전부 삭제. 삭제된 광고 수 반환."""
    with connect() as conn:
        deleted = conn.execute(
            "DELETE FROM ads WHERE page_id = ?", (str(page_id),)
        ).rowcount
        conn.execute(
            "DELETE FROM annotations WHERE ad_id NOT IN (SELECT ad_id FROM ads)"
        )
        conn.execute(
            "DELETE FROM competitors WHERE page_id = ?", (str(page_id),)
        )
    return deleted


def list_competitors(only_active: bool = True) -> list[sqlite3.Row]:
    with connect() as conn:
        q = "SELECT * FROM competitors"
        if only_active:
            q += " WHERE is_active = 1"
        q += " ORDER BY added_at DESC"
        return list(conn.execute(q))


def upsert_ad(ad: dict[str, Any]) -> tuple[bool, bool]:
    """Returns (was_inserted, was_updated). was_inserted=True iff brand new."""
    now = datetime.now().isoformat(timespec="seconds")
    with connect() as conn:
        existing = conn.execute(
            "SELECT ad_id FROM ads WHERE ad_id = ?", (ad["ad_id"],)
        ).fetchone()

        if existing:
            conn.execute(
                """UPDATE ads SET
                     caption = ?, cta_text = ?, landing_url = ?, display_url = ?,
                     platforms = ?, active_days = ?, is_active = ?, has_video = ?,
                     media_paths = ?, media_urls = ?, last_seen_at = ?, raw_json = ?
                   WHERE ad_id = ?""",
                (
                    ad.get("caption"),
                    ad.get("cta_text"),
                    ad.get("landing_url"),
                    ad.get("display_url"),
                    json.dumps(ad.get("platforms", []), ensure_ascii=False),
                    ad.get("active_days"),
                    int(bool(ad.get("is_active", True))),
                    int(bool(ad.get("has_video", False))),
                    json.dumps(ad.get("media_paths", []), ensure_ascii=False),
                    json.dumps(ad.get("media_urls", []), ensure_ascii=False),
                    now,
                    json.dumps(ad.get("raw", {}), ensure_ascii=False),
                    ad["ad_id"],
                ),
            )
            return False, True

        conn.execute(
            """INSERT INTO ads (
                 ad_id, page_id, page_name, caption, cta_text, landing_url, display_url,
                 platforms, start_date, active_days, is_active, has_video,
                 media_paths, media_urls, first_seen_at, last_seen_at, raw_json
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                ad["ad_id"],
                ad.get("page_id"),
                ad.get("page_name"),
                ad.get("caption"),
                ad.get("cta_text"),
                ad.get("landing_url"),
                ad.get("display_url"),
                json.dumps(ad.get("platforms", []), ensure_ascii=False),
                ad.get("start_date"),
                ad.get("active_days"),
                int(bool(ad.get("is_active", True))),
                int(bool(ad.get("has_video", False))),
                json.dumps(ad.get("media_paths", []), ensure_ascii=False),
                json.dumps(ad.get("media_urls", []), ensure_ascii=False),
                now,
                now,
                json.dumps(ad.get("raw", {}), ensure_ascii=False),
            ),
        )
        return True, False


def log_run(page_id: str, mode: str, ads_found: int, ads_new: int,
            started_at: datetime, status: str = "ok", error: str | None = None) -> None:
    with connect() as conn:
        conn.execute(
            """INSERT INTO scrape_runs
               (started_at, finished_at, page_id, mode, ads_found, ads_new, status, error)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                started_at.isoformat(timespec="seconds"),
                datetime.now().isoformat(timespec="seconds"),
                page_id, mode, ads_found, ads_new, status, error,
            ),
        )


# --- 조회 함수 (대시보드용) ---

def ads_first_seen_on(day: date) -> list[dict]:
    """그 날짜에 우리 DB에 처음 들어온 광고."""
    start = datetime.combine(day, datetime.min.time()).isoformat(timespec="seconds")
    end = datetime.combine(day + timedelta(days=1), datetime.min.time()).isoformat(timespec="seconds")
    with connect() as conn:
        rows = conn.execute(
            """SELECT a.*, ann.is_winner_candidate, ann.tags, ann.memo
               FROM ads a
               LEFT JOIN annotations ann ON ann.ad_id = a.ad_id
               WHERE a.first_seen_at >= ? AND a.first_seen_at < ?
               ORDER BY a.first_seen_at DESC""",
            (start, end),
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


def ads_active_for_at_least(days: int) -> list[dict]:
    """active_days >= days 인 활성 광고."""
    with connect() as conn:
        rows = conn.execute(
            """SELECT a.*, ann.is_winner_candidate, ann.tags, ann.memo
               FROM ads a
               LEFT JOIN annotations ann ON ann.ad_id = a.ad_id
               WHERE a.is_active = 1 AND a.active_days >= ?
               ORDER BY a.active_days DESC""",
            (days,),
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


def ads_by_page(page_id: str) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            """SELECT a.*, ann.is_winner_candidate, ann.tags, ann.memo
               FROM ads a
               LEFT JOIN annotations ann ON ann.ad_id = a.ad_id
               WHERE a.page_id = ?
               ORDER BY a.start_date DESC""",
            (page_id,),
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


def winner_candidates() -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            """SELECT a.*, ann.is_winner_candidate, ann.tags, ann.memo
               FROM ads a
               INNER JOIN annotations ann ON ann.ad_id = a.ad_id
               WHERE ann.is_winner_candidate = 1
               ORDER BY ann.updated_at DESC"""
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


def get_all_favorite_ids() -> set:
    """찜한 모든 광고 ID를 한 번의 쿼리로 set으로 돌려준다."""
    with connect() as conn:
        rows = conn.execute(
            "SELECT ad_id FROM annotations WHERE is_winner_candidate = 1"
        ).fetchall()
    return {row["ad_id"] for row in rows}


def is_favorite(ad_id: str) -> bool:
    with connect() as conn:
        row = conn.execute(
            "SELECT is_winner_candidate FROM annotations WHERE ad_id = ?",
            (ad_id,),
        ).fetchone()
    return bool(row and row["is_winner_candidate"])


def toggle_favorite(ad_id: str) -> bool:
    """찜 상태를 뒤집고 새 상태를 돌려준다."""
    now = datetime.now().isoformat(timespec="seconds")
    with connect() as conn:
        row = conn.execute(
            "SELECT is_winner_candidate, tags, memo FROM annotations WHERE ad_id = ?",
            (ad_id,),
        ).fetchone()
        new_state = 0 if (row and row["is_winner_candidate"]) else 1
        conn.execute(
            """INSERT INTO annotations (ad_id, is_winner_candidate, tags, memo, updated_at)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(ad_id) DO UPDATE SET
                 is_winner_candidate = excluded.is_winner_candidate,
                 updated_at = excluded.updated_at""",
            (
                ad_id,
                new_state,
                row["tags"] if row else json.dumps([], ensure_ascii=False),
                row["memo"] if row else "",
                now,
            ),
        )
    return bool(new_state)


def update_annotation(ad_id: str, is_winner: bool, tags: list[str], memo: str) -> None:
    with connect() as conn:
        conn.execute(
            """INSERT INTO annotations (ad_id, is_winner_candidate, tags, memo, updated_at)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(ad_id) DO UPDATE SET
                 is_winner_candidate = excluded.is_winner_candidate,
                 tags = excluded.tags,
                 memo = excluded.memo,
                 updated_at = excluded.updated_at""",
            (ad_id, int(bool(is_winner)), json.dumps(tags, ensure_ascii=False), memo,
             datetime.now().isoformat(timespec="seconds")),
        )


def last_run_summary() -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            """SELECT page_id, MAX(finished_at) as last_run, status
               FROM scrape_runs
               GROUP BY page_id
               ORDER BY last_run DESC"""
        ).fetchall()
    return [dict(r) for r in rows]


def _row_to_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    for json_field in ("platforms", "media_paths", "media_urls", "tags", "raw_json"):
        if d.get(json_field):
            try:
                d[json_field] = json.loads(d[json_field])
            except (json.JSONDecodeError, TypeError):
                pass
    return d


if __name__ == "__main__":
    init_db()
    print(f"DB initialized at {DB_PATH}")
