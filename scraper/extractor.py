"""광고 라이브러리 GraphQL/HTML 응답에서 필드 추출.

광고 라이브러리는 GraphQL로 데이터를 받아오는데, 응답 구조가 자주 바뀜.
"흔히 등장하는 필드 이름"을 여러 가능성으로 시도하는 방어적 코드.

⚠️ 메타가 응답 스키마 바꾸면 여기가 가장 먼저 깨짐. 셀렉터/필드명을 한 곳에 모음.
"""
from __future__ import annotations

import re
from datetime import datetime, date
from typing import Any


def _walk(obj: Any, key_names: tuple[str, ...]) -> list[Any]:
    """obj 안의 모든 깊이를 탐색하며 key_names 중 하나와 매칭되는 값들 수집."""
    found: list[Any] = []

    def visit(node):
        if isinstance(node, dict):
            for k, v in node.items():
                if k in key_names:
                    found.append(v)
                visit(v)
        elif isinstance(node, list):
            for item in node:
                visit(item)

    visit(obj)
    return found


def extract_ads_from_graphql(payload: dict) -> list[dict]:
    """GraphQL 응답 한 덩어리에서 광고 카드들을 뽑아냄."""
    cards: list[dict] = []
    # 메타가 사용해온 컨테이너 이름들 — 자주 바뀌니 후보 여러 개
    containers = _walk(
        payload,
        ("ad_archive_id", "adArchiveID", "adArchiveId"),
    )
    if not containers:
        return cards

    # 광고 카드 노드를 찾으려면 ad_archive_id를 가진 dict를 찾아야 함
    def find_ad_nodes(node, acc):
        if isinstance(node, dict):
            if any(k in node for k in ("ad_archive_id", "adArchiveID", "adArchiveId")):
                acc.append(node)
            for v in node.values():
                find_ad_nodes(v, acc)
        elif isinstance(node, list):
            for item in node:
                find_ad_nodes(item, acc)

    nodes: list[dict] = []
    find_ad_nodes(payload, nodes)

    for node in nodes:
        try:
            cards.append(_node_to_ad(node))
        except Exception as e:
            # 한 광고가 깨져도 다음 광고는 계속
            cards.append({"_extract_error": str(e), "raw": node})
    return cards


def _first_value(node: dict, *keys: str, default=None):
    for k in keys:
        if k in node and node[k] is not None:
            return node[k]
    return default


def _node_to_ad(node: dict) -> dict:
    ad_id = str(_first_value(node, "ad_archive_id", "adArchiveID", "adArchiveId", default=""))
    snapshot = _first_value(node, "snapshot", default={}) or {}
    page_id = str(
        _first_value(snapshot, "page_id", "pageId", default="")
        or _first_value(node, "page_id", default="")
    )
    page_name = (
        _first_value(snapshot, "page_name", "pageName", default="")
        or _first_value(node, "page_name", default="")
    )

    # 캡션: snapshot.body.text
    body = snapshot.get("body") or {}
    caption = (body.get("text") if isinstance(body, dict) else body) or ""

    cta_text = _first_value(snapshot, "cta_text", "ctaText", default="") or ""
    landing_url = _first_value(snapshot, "link_url", "linkUrl", default="") or ""
    # snapshot의 "caption" 필드는 표시용 도메인(display URL)
    display_url = snapshot.get("caption") or ""

    # 플랫폼
    platforms = [p.lower() for p in (node.get("publisher_platform") or []) if isinstance(p, str)]

    # 게재 시작일
    raw_start = node.get("start_date")
    start_date = None
    start_datetime = None
    if raw_start:
        try:
            dt = datetime.fromtimestamp(int(raw_start))
            start_datetime = dt
            start_date = dt.date().isoformat()
        except Exception:
            pass

    # 활성 여부 & 게재일수
    is_active = bool(node.get("is_active", True))
    active_days = None
    if raw_start:
        try:
            start_d = datetime.fromtimestamp(int(raw_start)).date()
            if is_active:
                active_days = (date.today() - start_d).days
            else:
                raw_end = node.get("end_date")
                end_d = datetime.fromtimestamp(int(raw_end)).date() if raw_end else date.today()
                active_days = (end_d - start_d).days
        except Exception:
            pass

    # 소재(이미지 / 영상)
    media_urls: list[dict] = []

    for img in (snapshot.get("images") or []):
        if isinstance(img, dict):
            url = (
                img.get("original_image_url")
                or img.get("resized_image_url")
                or img.get("url")
                or ""
            )
            if url:
                media_urls.append({"type": "image", "url": url})
        elif isinstance(img, str) and img:
            media_urls.append({"type": "image", "url": img})

    videos = snapshot.get("videos") or []
    for vid in videos:
        if isinstance(vid, dict):
            url = vid.get("video_hd_url") or vid.get("video_sd_url") or ""
            if url:
                entry: dict = {"type": "video", "url": url}
                preview = vid.get("video_preview_image_url") or ""
                if preview:
                    entry["preview"] = preview
                media_urls.append(entry)

    # DPA / 카드형 광고: snapshot.cards 에 미디어가 들어있는 경우 처리
    for card in (snapshot.get("cards") or []):
        if not isinstance(card, dict):
            continue
        vid_url = card.get("video_hd_url") or card.get("video_sd_url") or ""
        if vid_url:
            entry = {"type": "video", "url": vid_url}
            preview = card.get("video_preview_image_url") or ""
            if preview:
                entry["preview"] = preview
            media_urls.append(entry)
        else:
            img_url = card.get("original_image_url") or card.get("resized_image_url") or ""
            if img_url:
                media_urls.append({"type": "image", "url": img_url})

    has_video = bool(videos) or (snapshot.get("display_format") or "").upper() == "VIDEO"

    return {
        "ad_id": ad_id,
        "page_id": page_id,
        "page_name": page_name,
        "caption": caption,
        "cta_text": cta_text,
        "landing_url": landing_url,
        "display_url": display_url,
        "platforms": platforms,
        "start_date": start_date,
        "start_datetime": start_datetime,
        "active_days": active_days,
        "is_active": is_active,
        "has_video": has_video,
        "media_urls": media_urls,
        "raw": node,
    }
