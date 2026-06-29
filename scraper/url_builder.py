"""광고 라이브러리 URL 빌더.

두 가지 정렬 모드:
- relevancy_monthly_grouped: "최신/관련도순" — 어제 새로 올라온 광고 찾기 좋음
- total_impressions: "노출수 많은 순" — 위너 후보
"""
from __future__ import annotations

import re
from urllib.parse import urlencode


def parse_page_id(raw: str) -> str | None:
    """광고 라이브러리 URL(또는 페이지 ID 숫자)에서 page_id를 뽑아낸다.

    허용 입력:
      - 순수 숫자 ID            → "1947160905536967"
      - ...?view_all_page_id=…  → 그 숫자
      - .../pages/이름/123…     → 그 숫자
    못 찾으면 None.
    """
    raw = (raw or "").strip()
    if not raw:
        return None
    if raw.isdigit():
        return raw
    m = re.search(r"view_all_page_id=(\d+)", raw)
    if m:
        return m.group(1)
    m = re.search(r"/pages/[^/]+/(\d+)", raw)
    if m:
        return m.group(1)
    return None


def page_url(page_id: str, mode: str = "relevancy_monthly_grouped",
             country: str = "KR") -> str:
    """경쟁사 페이지의 활성 광고 URL.

    mode:
      - "relevancy_monthly_grouped" → 신규/관련도순
      - "total_impressions" → 노출수 많은 순 (위너 후보)
    """
    assert mode in ("relevancy_monthly_grouped", "total_impressions"), \
        f"Unknown mode: {mode}"

    params = {
        "active_status": "active",
        "ad_type": "all",
        "country": country,
        "is_targeted_country": "false",
        "media_type": "all",
        "search_type": "page",
        "sort_data[direction]": "desc",
        "sort_data[mode]": mode,
        "source": "nav-header",
        "view_all_page_id": page_id,
    }
    return f"https://www.facebook.com/ads/library/?{urlencode(params)}"


def ad_detail_url(ad_id: str) -> str:
    return f"https://www.facebook.com/ads/library/?id={ad_id}"
