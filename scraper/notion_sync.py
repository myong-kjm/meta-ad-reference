"""노션 직접 적재 모듈.

수집된 광고를 Notion API로 직접 데이터베이스에 추가한다.
중복은 ad_id 기준으로 자동 차단.

환경변수:
    NOTION_TOKEN          — Notion Internal Integration 토큰 (필수)
    NOTION_DATABASE_ID    — 광고 레퍼런스 DB의 data source ID (필수)
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any
from urllib import request, error

NOTION_VERSION = "2022-06-28"
NOTION_API = "https://api.notion.com/v1"


class NotionError(RuntimeError):
    pass


def _token() -> str:
    token = os.getenv("NOTION_TOKEN")
    if not token:
        raise NotionError("NOTION_TOKEN 환경변수가 없습니다")
    return token


def _database_id() -> str:
    db = os.getenv("NOTION_DATABASE_ID")
    if not db:
        raise NotionError("NOTION_DATABASE_ID 환경변수가 없습니다")
    return db


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {_token()}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }


def _api_call(method: str, path: str, body: dict | None = None, retry: int = 2) -> dict:
    url = f"{NOTION_API}{path}"
    data = json.dumps(body).encode("utf-8") if body else None
    req = request.Request(url, data=data, method=method, headers=_headers())
    last_err = None
    for attempt in range(retry + 1):
        try:
            with request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except error.HTTPError as e:
            body_text = e.read().decode("utf-8", errors="ignore")
            last_err = NotionError(f"Notion {method} {path} {e.code}: {body_text[:300]}")
            if e.code in (429, 500, 502, 503) and attempt < retry:
                time.sleep(2 ** attempt)
                continue
            raise last_err from e
        except Exception as e:
            last_err = NotionError(f"Notion {method} {path} 실패: {e}")
            if attempt < retry:
                time.sleep(2 ** attempt)
                continue
            raise last_err from e
    raise last_err or NotionError("알 수 없는 오류")


def find_existing_ad_id(ad_id: str) -> str | None:
    """이미 노션에 존재하는 광고면 페이지 ID를 반환."""
    res = _api_call(
        "POST",
        f"/databases/{_database_id()}/query",
        {
            "filter": {"property": "ad_id", "rich_text": {"equals": ad_id}},
            "page_size": 1,
        },
    )
    results = res.get("results") or []
    return results[0]["id"] if results else None


def _platforms_multiselect(platforms: list[str]) -> list[dict]:
    valid = {"FACEBOOK", "INSTAGRAM", "MESSENGER", "AUDIENCE_NETWORK", "THREADS"}
    return [{"name": p.upper()} for p in platforms if p.upper() in valid]


def _ad_library_url(ad_id: str) -> str:
    return f"https://www.facebook.com/ads/library/?id={ad_id}"


def _build_page_properties(ad: dict[str, Any]) -> dict[str, Any]:
    ad_id = str(ad.get("ad_id") or "")
    page_name = ad.get("page_name") or ad.get("page_id") or ""
    short_id = ad_id[-6:] if ad_id else "광고"
    title = f"{page_name.split(' - ')[0]} · {short_id}"

    platforms = ad.get("platforms") or []
    if isinstance(platforms, str):
        try:
            platforms = json.loads(platforms)
        except json.JSONDecodeError:
            platforms = []

    caption = (ad.get("caption") or "").strip()[:1900]
    cta = ad.get("cta_text") or ""
    landing = ad.get("landing_url") or ""
    start_date = ad.get("start_date") or None
    active_days = ad.get("active_days") or 0
    is_active = bool(ad.get("is_active"))
    has_video = bool(ad.get("has_video"))
    first_seen = ad.get("first_seen_at") or None
    last_seen = ad.get("last_seen_at") or None

    props: dict[str, Any] = {
        "광고": {"title": [{"text": {"content": title}}]},
        "ad_id": {"rich_text": [{"text": {"content": ad_id}}]},
        "경쟁사": {"rich_text": [{"text": {"content": page_name}}]},
        "게재일수": {"number": int(active_days) if active_days else 0},
        "활성": {"select": {"name": "ACTIVE" if is_active else "INACTIVE"}},
        "영상": {"checkbox": has_video},
        "캡션": {"rich_text": [{"text": {"content": caption}}]} if caption else {"rich_text": []},
        "CTA": {"rich_text": [{"text": {"content": cta}}]} if cta else {"rich_text": []},
        "광고 라이브러리": {"url": _ad_library_url(ad_id)} if ad_id else {"url": None},
    }
    if landing:
        props["랜딩 URL"] = {"url": landing}
    if platforms:
        props["플랫폼"] = {"multi_select": _platforms_multiselect(platforms)}
    if start_date:
        props["게재 시작"] = {"date": {"start": start_date}}
    if first_seen:
        props["수집 일시"] = {"date": {"start": first_seen}}
    if last_seen:
        props["마지막 확인"] = {"date": {"start": last_seen}}

    return props


def _build_page_children(ad: dict[str, Any]) -> list[dict]:
    """페이지 본문 블록 — 미디어 + 캡션 + 빠른링크."""
    raw = ad.get("raw_json") or {}
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            raw = {}
    snap = raw.get("snapshot") or {}

    images = []
    for img in snap.get("images") or []:
        if isinstance(img, dict):
            u = img.get("original_image_url") or img.get("resized_image_url")
            if u:
                images.append(u)

    videos = []
    for v in snap.get("videos") or []:
        if isinstance(v, dict):
            videos.append({
                "sd": v.get("video_sd_url"),
                "hd": v.get("video_hd_url"),
                "preview": v.get("video_preview_image_url"),
            })

    caption = (ad.get("caption") or "").strip()
    ad_id = str(ad.get("ad_id") or "")
    landing = ad.get("landing_url") or ""
    blocks: list[dict] = []

    if images:
        blocks.append({"object": "block", "type": "heading_2", "heading_2": {"rich_text": [{"text": {"content": "소재 (이미지)"}}]}})
        for u in images[:5]:
            blocks.append({"object": "block", "type": "image", "image": {"type": "external", "external": {"url": u}}})

    if videos:
        blocks.append({"object": "block", "type": "heading_2", "heading_2": {"rich_text": [{"text": {"content": "소재 (영상)"}}]}})
        for v in videos[:3]:
            src = v.get("sd") or v.get("hd")
            if src:
                blocks.append({"object": "block", "type": "video", "video": {"type": "external", "external": {"url": src}}})
            if v.get("preview"):
                blocks.append({"object": "block", "type": "image", "image": {"type": "external", "external": {"url": v["preview"]}}})

    if caption:
        blocks.append({"object": "block", "type": "heading_2", "heading_2": {"rich_text": [{"text": {"content": "캡션"}}]}})
        # 한 블록당 2000자 제한
        for chunk_start in range(0, min(len(caption), 5800), 1900):
            chunk = caption[chunk_start:chunk_start + 1900]
            blocks.append({
                "object": "block",
                "type": "quote",
                "quote": {"rich_text": [{"text": {"content": chunk}}]},
            })

    blocks.append({"object": "block", "type": "heading_2", "heading_2": {"rich_text": [{"text": {"content": "빠른 링크"}}]}})
    blocks.append({
        "object": "block",
        "type": "bulleted_list_item",
        "bulleted_list_item": {"rich_text": [
            {"text": {"content": "📺 페이스북 광고 라이브러리에서 열기", "link": {"url": _ad_library_url(ad_id)}}}
        ]},
    })
    if landing:
        blocks.append({
            "object": "block",
            "type": "bulleted_list_item",
            "bulleted_list_item": {"rich_text": [
                {"text": {"content": "🛒 랜딩페이지 열기", "link": {"url": landing}}}
            ]},
        })

    return blocks


def upsert_ad_to_notion(ad: dict[str, Any]) -> tuple[bool, str]:
    """광고 1건을 노션에 적재. (was_new, page_id) 반환."""
    ad_id = str(ad.get("ad_id") or "")
    if not ad_id:
        raise NotionError("ad_id가 없는 광고")

    existing_page_id = find_existing_ad_id(ad_id)
    props = _build_page_properties(ad)

    if existing_page_id:
        _api_call("PATCH", f"/pages/{existing_page_id}", {"properties": props})
        return False, existing_page_id

    icon = "🎬" if ad.get("has_video") else "🖼️"
    page = _api_call(
        "POST",
        "/pages",
        {
            "parent": {"database_id": _database_id()},
            "icon": {"type": "emoji", "emoji": icon},
            "properties": props,
            "children": _build_page_children(ad),
        },
    )
    return True, page["id"]


def sync_ads(ads: list[dict[str, Any]]) -> dict[str, int]:
    """광고 리스트를 노션 DB에 일괄 적재.

    Returns: {"new": N, "updated": M, "errors": K}
    """
    new = updated = errors = 0
    for ad in ads:
        if not ad.get("ad_id"):
            continue
        try:
            was_new, _ = upsert_ad_to_notion(ad)
            if was_new:
                new += 1
                print(f"    ✓ 노션 신규 추가: {ad.get('page_name', '')} {ad['ad_id'][-6:]}")
            else:
                updated += 1
        except NotionError as e:
            errors += 1
            print(f"    ⚠️  노션 적재 실패 ({ad.get('ad_id')}): {e}")
        except Exception as e:
            errors += 1
            print(f"    ⚠️  노션 적재 예외 ({ad.get('ad_id')}): {e}")
        time.sleep(0.35)  # rate limit 회피
    return {"new": new, "updated": updated, "errors": errors}


def is_enabled() -> bool:
    return bool(os.getenv("NOTION_TOKEN") and os.getenv("NOTION_DATABASE_ID"))


if __name__ == "__main__":
    # 간단한 자가진단
    print("NOTION_TOKEN:", "설정됨" if os.getenv("NOTION_TOKEN") else "없음")
    print("NOTION_DATABASE_ID:", os.getenv("NOTION_DATABASE_ID") or "없음")
    if is_enabled():
        try:
            res = _api_call("GET", f"/databases/{_database_id()}")
            print("DB 확인:", res.get("title", [{}])[0].get("plain_text") if res.get("title") else res.get("id"))
        except Exception as e:
            print("DB 접근 실패:", e)
