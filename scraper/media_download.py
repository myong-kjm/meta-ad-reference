"""광고 미디어(영상/이미지) 로컬 다운로드.

URL 한 개씩 받아서 data/media/<page_id>/<ad_id>/ 아래 저장.
- 같은 파일 중복 다운로드 X
- 영상은 .mp4, 이미지는 .jpg로 통일 (확장자 자동 추정)
- 요청 사이 짧은 sleep
"""
from __future__ import annotations

import hashlib
import random
import time
from pathlib import Path
from urllib.parse import urlparse

import requests

MEDIA_ROOT = Path(__file__).resolve().parent.parent / "data" / "media"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/132.0.0.0 Safari/537.36"
    ),
    "Accept": "*/*",
    "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
}


def _ext_for(url: str, media_type: str) -> str:
    path = urlparse(url).path.lower()
    if media_type == "video":
        if path.endswith(".mp4"):
            return ".mp4"
        if path.endswith(".mov"):
            return ".mov"
        return ".mp4"
    # image
    for ext in (".jpg", ".jpeg", ".png", ".webp", ".gif"):
        if path.endswith(ext):
            return ext
    return ".jpg"


def _short_hash(s: str, n: int = 10) -> str:
    return hashlib.sha1(s.encode()).hexdigest()[:n]


def download_media(media_items: list[dict], page_id: str, ad_id: str) -> list[str]:
    """미디어 URL 목록 → 로컬 상대 경로 목록 (DB에 저장할 형태)."""
    target_dir = MEDIA_ROOT / str(page_id) / str(ad_id)
    target_dir.mkdir(parents=True, exist_ok=True)

    rel_paths: list[str] = []
    for idx, item in enumerate(media_items):
        url = item.get("url")
        media_type = item.get("type", "image")
        if not url:
            continue

        ext = _ext_for(url, media_type)
        filename = f"{media_type}_{idx:02d}_{_short_hash(url)}{ext}"
        target = target_dir / filename

        if not target.exists():
            try:
                resp = requests.get(url, headers=HEADERS, timeout=30, stream=True)
                resp.raise_for_status()
                with open(target, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=64 * 1024):
                        if chunk:
                            f.write(chunk)
                time.sleep(random.uniform(0.4, 1.2))
            except Exception as e:
                print(f"    ⚠️  미디어 다운로드 실패 ({url[:60]}...): {e}")
                continue

        rel_paths.append(str(target.relative_to(MEDIA_ROOT.parent)))

        # 영상이면 미리보기 이미지도 같이 받기
        preview_url = item.get("preview")
        if preview_url and media_type == "video":
            preview_name = f"preview_{idx:02d}_{_short_hash(preview_url)}.jpg"
            preview_target = target_dir / preview_name
            if not preview_target.exists():
                try:
                    resp = requests.get(preview_url, headers=HEADERS, timeout=20)
                    resp.raise_for_status()
                    preview_target.write_bytes(resp.content)
                except Exception:
                    pass
            if preview_target.exists():
                rel_paths.append(str(preview_target.relative_to(MEDIA_ROOT.parent)))

    return rel_paths
