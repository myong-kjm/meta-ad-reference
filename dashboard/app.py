"""광고 레퍼런스 대시보드 — Streamlit.

실행: streamlit run dashboard/app.py
"""
from __future__ import annotations

import json
import subprocess
import sys
import zipfile
from io import BytesIO
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scraper import db

DATA_ROOT = ROOT / "data"
CONFIG_PATH = ROOT / "config.json"

st.set_page_config(
    page_title="META 광고 레퍼런스 수집",
    page_icon="🌸",
    layout="wide",
)

db.init_db()



st.markdown(
    """
    <style>
    @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.css');

    /* === 전체 폰트: Pretendard === */
    html, body {
        font-family: 'Pretendard', -apple-system, BlinkMacSystemFont, sans-serif !important;
    }

    .block-container { padding-top: 4.5rem; }
    [data-testid="stSidebar"] { min-width: 320px; }
    div[data-testid="stMetricValue"] { font-size: 1.55rem; }

    /* === 메인 영역: 밝은 배경 #F5F3F3 + 어두운 텍스트 === */
    [data-testid="stMain"],
    section.main,
    [data-testid="stAppViewContainer"] > .main,
    [data-testid="stHeader"] {
        background: #F5F3F3 !important;
    }
    [data-testid="stMain"] h1,
    [data-testid="stMain"] h2,
    [data-testid="stMain"] h3,
    [data-testid="stMain"] h4,
    [data-testid="stMain"] [data-testid="stMarkdownContainer"] p,
    [data-testid="stMain"] [data-testid="stMetricLabel"],
    [data-testid="stMain"] [data-testid="stMetricValue"],
    [data-testid="stMain"] [data-baseweb="tab"] > div {
        color: #1a1a1a !important;
    }
    [data-testid="stMain"] [data-testid="stCaptionContainer"] {
        color: #555 !important;
    }

    /* 일반 버튼은 본래의 흰 글자로 — 단, 탭(role=tab)은 제외 */
    [data-testid="stMain"] button:not([role="tab"]),
    [data-testid="stMain"] button:not([role="tab"]) *,
    [data-testid="stMain"] button:not([role="tab"]) p,
    [data-testid="stMain"] button:not([role="tab"]) span,
    [data-testid="stMain"] button:not([role="tab"]) div,
    [data-testid="stMain"] button:not([role="tab"]) [data-testid="stMarkdownContainer"],
    [data-testid="stMain"] button:not([role="tab"]) [data-testid="stMarkdownContainer"] p {
        color: #fafafa !important;
    }
    /* 상단 헤더의 Rerun 등 액션 텍스트 */
    [data-testid="stHeader"] a,
    [data-testid="stHeader"] span,
    [data-testid="stHeader"] button {
        color: #1a1a1a !important;
    }

    /* === 메트릭 카드 === */
    [data-testid="stMain"] [data-testid="stMetric"] {
        background: #ffffff;
        border: 1px solid #e6e3e3;
        border-radius: 14px;
        padding: 18px 22px;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
    }
    [data-testid="stMain"] [data-testid="stMetric"] [data-testid="stMetricLabel"] {
        color: #6b6b6b !important;
        font-size: 0.85rem;
    }
    [data-testid="stMain"] [data-testid="stMetric"] [data-testid="stMetricValue"] {
        color: #111 !important;
        font-weight: 700;
    }

    /* === 제목: Pretendard 굵게 === */
    [data-testid="stMain"] h1,
    [data-testid="stSidebar"] h1 {
        font-family: 'Pretendard', -apple-system, sans-serif !important;
        font-weight: 800 !important;
        letter-spacing: -0.5px;
    }

    /* === 사이드바 타이틀 === */
    [data-testid="stSidebar"] .sidebar-title {
        margin: 4px 0 18px 0;
        font-family: 'Pretendard', -apple-system, sans-serif;
        font-weight: 800;
        font-size: 1.62rem;
        line-height: 1.1;
        letter-spacing: -1px;
        color: #ffffff;
    }

    /* === 탭 라벨 === */
    [data-testid="stMain"] button[role="tab"],
    [data-testid="stMain"] button[role="tab"] *,
    [data-testid="stMain"] [data-baseweb="tab-list"] button,
    [data-testid="stMain"] [data-baseweb="tab-list"] button * {
        color: #1a1a1a !important;
        font-size: 1.08rem !important;
        font-weight: 700 !important;
    }
    [data-testid="stMain"] button[role="tab"][aria-selected="false"],
    [data-testid="stMain"] button[role="tab"][aria-selected="false"] * {
        color: #6b6b6b !important;
    }
    [data-testid="stMain"] [data-baseweb="tab-list"] {
        border-bottom: 1px solid #d6d3d3 !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <style>
    /* === 광고 상세 모달 === */
    /* 모달 안 영상: 세로 영상도 한 화면에 들어오게 max-height 제한 */
    [data-testid="stDialog"] video,
    div[role="dialog"] video {
        max-height: 70vh !important;
        width: auto !important;
        max-width: 100% !important;
        display: block;
        margin: 0 auto;
    }
    /* video 컨테이너 가운데 정렬 */
    [data-testid="stDialog"] [data-testid="stVideo"],
    div[role="dialog"] [data-testid="stVideo"] {
        display: flex;
        justify-content: center;
        background: #000;
        border-radius: 12px;
        overflow: hidden;
    }
    /* 이미지도 동일하게 한 화면 내로 */
    [data-testid="stDialog"] [data-testid="stImage"] img,
    div[role="dialog"] [data-testid="stImage"] img {
        max-height: 70vh !important;
        width: auto !important;
        max-width: 100% !important;
        margin: 0 auto;
        display: block;
    }

    /* 닫기 X 버튼 크게 */
    [data-testid="stDialog"] button[kind="header"] svg,
    div[role="dialog"] button[kind="header"] svg,
    [data-testid="stDialog"] [aria-label*="Close"] svg,
    div[role="dialog"] [aria-label*="Close"] svg,
    [data-testid="stDialog"] header button svg,
    div[role="dialog"] header button svg {
        width: 32px !important;
        height: 32px !important;
        stroke-width: 2.2 !important;
    }
    [data-testid="stDialog"] button[kind="header"],
    div[role="dialog"] button[kind="header"],
    [data-testid="stDialog"] [aria-label*="Close"],
    div[role="dialog"] [aria-label*="Close"],
    [data-testid="stDialog"] header button,
    div[role="dialog"] header button {
        width: 48px !important;
        height: 48px !important;
        padding: 8px !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def media_abspath(rel_path: str) -> Path:
    """DB에 저장된 상대 경로를 절대 경로로 바꾼다."""
    if rel_path.startswith("data/"):
        return DATA_ROOT / rel_path[len("data/"):]
    return DATA_ROOT / rel_path


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        return {}
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def notion_db_url(config: dict) -> str | None:
    return config.get("notion", {}).get("database_url")


def notion_parent_url(config: dict) -> str | None:
    return config.get("notion", {}).get("parent_page_url")


def _remove_competitor_from_config(page_id: str) -> None:
    """config.json 경쟁사 목록에서 해당 page_id 항목 제거."""
    if not CONFIG_PATH.exists():
        return
    try:
        cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        cfg["competitors"] = [
            c for c in cfg.get("competitors", [])
            if str(c.get("page_id")) != str(page_id)
        ]
        CONFIG_PATH.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


@st.dialog("경쟁사 삭제")
def confirm_delete_competitor(page_id: str, page_name: str) -> None:
    st.warning(f"**{page_name}** 의 모든 수집 광고를 함께 삭제합니다.")
    st.caption("이 작업은 되돌릴 수 없어요.")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("삭제", type="primary", width="stretch", key="confirm_del_btn"):
            deleted = db.delete_competitor(page_id)
            _remove_competitor_from_config(page_id)
            st.success(f"삭제 완료 — 광고 {deleted}개 제거됨")
            if st.button("닫기", key="close_del_btn"):
                st.rerun(scope="app")
    with col2:
        if st.button("취소", width="stretch", key="cancel_del_btn"):
            st.rerun(scope="app")


@st.dialog("신규 광고 수집 중")
def run_collect_dialog(cmd: list[str]) -> None:
    """'지금 수집' 실행을 모달로 띄우고, 진행 로그를 실시간으로 보여준다."""
    st.markdown("### ⏳ 신규 광고 수집 중입니다")
    st.write("잠시만 기다려주세요 — 페이지 열기 → 스크롤 → 추출 → 저장 순으로 진행돼요.")
    st.caption("창을 닫지 말고 그대로 두세요. (봇 회피용 휴식 때문에 30초~1분 걸릴 수 있어요)")
    log_box = st.empty()
    lines: list[str] = []
    rc = -1
    try:
        proc = subprocess.Popen(
            cmd,
            cwd=str(ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
        for line in proc.stdout:  # type: ignore[union-attr]
            lines.append(line.rstrip())
            log_box.code("\n".join(lines[-16:]))
        rc = proc.wait()
    except Exception as e:
        st.error(f"수집 실행 실패: {e}")

    joined = "\n".join(lines)
    if rc == 0 and ("신규" in joined or "수집" in joined) and " 0개" not in joined:
        st.success("수집 완료 ✓ — 이름·결과가 갱신됐어요")
    elif rc == 0:
        st.warning("수집은 끝났지만 새 광고가 0건이에요. 봇 차단/일시 제한일 수 있어요. 잠시 후 다시 시도하세요.")
    else:
        st.error(f"수집 종료 (코드 {rc}) — 로그를 확인하세요. 봇 차단이면 24시간 후 재시도 권장.")

    if st.button("닫고 새로고침", type="primary", width="stretch"):
        st.rerun(scope="app")


def as_list(value) -> list:
    if not value:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
            return decoded if isinstance(decoded, list) else []
        except json.JSONDecodeError:
            return []
    return []


def image_for_ad(ad: dict) -> str | None:
    """갤러리용 이미지: 로컬 파일 우선, 없으면 원본 URL 반환."""
    media_paths = as_list(ad.get("media_paths"))
    preferred = [p for p in media_paths if "preview_" in Path(p).name]
    preferred += [p for p in media_paths if "image_" in Path(p).name]

    for rel_path in preferred:
        path = media_abspath(rel_path)
        if path.exists():
            return str(path)

    # 로컬 파일 없으면 media_urls에서 URL 반환
    for item in as_list(ad.get("media_urls")):
        if isinstance(item, dict):
            if item.get("type") == "image":
                return item.get("url") or None
            if item.get("type") == "video" and item.get("preview"):
                return item["preview"]
        elif isinstance(item, str) and item:
            return item
    return None


def video_path_for_ad(ad: dict) -> Path | None:
    """광고의 영상 파일 경로(있을 경우)."""
    for rel in as_list(ad.get("media_paths")):
        name = Path(rel).name
        if name.endswith((".mp4", ".mov", ".webm")) or "video_" in name:
            path = media_abspath(rel)
            if path.exists() and path.is_file():
                return path
    return None


def thumbnail_path_for_ad(ad: dict) -> Path | None:
    """다운로드용 썸네일: preview_ 우선 → image_ → 첫 이미지."""
    media_paths = as_list(ad.get("media_paths"))
    for rel in media_paths:
        if "preview_" in Path(rel).name:
            path = media_abspath(rel)
            if path.exists():
                return path
    for rel in media_paths:
        name = Path(rel).name
        if "image_" in name or name.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
            path = media_abspath(rel)
            if path.exists():
                return path
    return None


def ad_library_url(ad_id: str) -> str:
    return f"https://www.facebook.com/ads/library/?id={ad_id}"


def media_files_for_ad(ad: dict) -> list[Path]:
    files = []
    for rel_path in as_list(ad.get("media_paths")):
        path = media_abspath(rel_path)
        if path.exists() and path.is_file():
            files.append(path)
    return files


def build_media_zip(ads: list[dict]) -> tuple[bytes | None, int]:
    """현재 필터 결과의 이미지/영상 파일을 ZIP으로 묶는다."""
    buffer = BytesIO()
    file_count = 0
    used_names: set[str] = set()

    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for ad in ads:
            page_name = str(ad.get("page_name") or ad.get("page_id") or "unknown")
            ad_id = str(ad.get("ad_id") or "unknown")
            safe_page = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in page_name)[:60]

            for path in media_files_for_ad(ad):
                arcname = f"{safe_page}/{ad_id}/{path.name}"
                if arcname in used_names:
                    arcname = f"{safe_page}/{ad_id}/{file_count}_{path.name}"
                used_names.add(arcname)
                zf.write(path, arcname)
                file_count += 1

    if file_count == 0:
        return None, 0
    return buffer.getvalue(), file_count


def load_ads_for_page(page_id: str | None) -> list[dict]:
    if page_id:
        return db.ads_by_page(page_id)

    ads: list[dict] = []
    for competitor in db.list_competitors(only_active=False):
        ads.extend(db.ads_by_page(competitor["page_id"]))
    return ads


def to_frame(ads: list[dict]) -> pd.DataFrame:
    rows = []
    for ad in ads:
        rows.append(
            {
                "ad_id": ad.get("ad_id"),
                "page_id": ad.get("page_id"),
                "page_name": ad.get("page_name") or ad.get("page_id"),
                "start_date": pd.to_datetime(ad.get("start_date"), errors="coerce"),
                "active_days": pd.to_numeric(ad.get("active_days"), errors="coerce"),
                "is_active": bool(ad.get("is_active")),
                "has_video": bool(ad.get("has_video")),
                "first_seen_at": pd.to_datetime(ad.get("first_seen_at"), errors="coerce"),
                "caption": ad.get("caption") or "",
            }
        )
    return pd.DataFrame(rows)


# ============================================================================
# 🧩 [같이 만들 곳 1 · 필수] 사이드바 필터 기능
# ----------------------------------------------------------------------------
# 지금은 "받은 광고를 그대로 다 돌려주는" 빈 상태예요.
# 그래서 대시보드는 멀쩡히 켜지지만, 사이드바의 필터(활성/영상/최소 게재일)를
# 아무리 움직여도 목록이 바뀌지 않습니다. ← 이걸 클로드 코드랑 같이 채웁니다.
#
# 이 함수가 하는 일(채우고 나면):
#   - ads        : 광고 목록 (각 광고는 사전 dict. 예: ad["is_active"], ad["has_video"], ad["active_days"], ad["start_date"])
#   - start, end : 게재 시작일 범위 (없으면 None)
#   - active_filter : "전체" / "활성만" / "비활성만"
#   - media_filter  : "전체" / "이미지" / "영상"
#   - min_active_days : 이 일수보다 적게 게재된 광고는 빼기 (위너 후보 거르기)
#   → 조건에 맞는 광고만 골라서 돌려주기
#
# 👉 워크샵 가이드(워크샵-가이드.md)의 "1단계" 프롬프트를 그대로 복사해서
#    클로드 코드에 붙여넣으면 이 함수를 완성해 줍니다.
# ============================================================================
def apply_filters(ads: list[dict], start: date | None, end: date | None,
                  active_filter: str, media_filter: str, min_active_days: int) -> list[dict]:
    result = []
    for ad in ads:
        if active_filter == "활성만" and not ad.get("is_active"):
            continue
        if active_filter == "비활성만" and ad.get("is_active"):
            continue

        if media_filter == "이미지" and ad.get("has_video"):
            continue
        if media_filter == "영상" and not ad.get("has_video"):
            continue

        active_days = int(ad.get("active_days") or 0)
        if active_days < min_active_days:
            continue

        if start or end:
            raw = ad.get("start_date")
            if raw:
                try:
                    ad_date = date.fromisoformat(str(raw)[:10])
                except ValueError:
                    ad_date = None
            else:
                ad_date = None
            if ad_date is None:
                continue
            if start and ad_date < start:
                continue
            if end and ad_date > end:
                continue

        result.append(ad)
    return result


def render_metrics(ads: list[dict]) -> None:
    total = len(ads)
    active = sum(1 for ad in ads if ad.get("is_active"))
    videos = sum(1 for ad in ads if ad.get("has_video"))
    avg_active_days = round(
        sum(int(ad.get("active_days") or 0) for ad in ads) / total, 1
    ) if total else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("레퍼런스", f"{total}개")
    c2.metric("활성 광고", f"{active}개")
    c3.metric("영상 소재", f"{videos}개")
    c4.metric("평균 게재일", f"{avg_active_days}일")


@st.dialog("광고 상세", width="large")
def show_ad_detail(ad: dict) -> None:
    """카드 클릭 시 열리는 광고 상세 모달."""
    ad_id = str(ad.get("ad_id") or "")
    page_name = ad.get("page_name") or ad.get("page_id") or ""
    caption = (ad.get("caption") or "").strip()
    cta = ad.get("cta_text") or ""
    landing = ad.get("landing_url") or ""
    start_date = ad.get("start_date") or ""
    active_days = ad.get("active_days") or 0
    is_active = bool(ad.get("is_active"))
    has_video = bool(ad.get("has_video"))

    video = video_path_for_ad(ad)
    thumb = thumbnail_path_for_ad(ad)

    col_media, col_info = st.columns([1.45, 1])

    # URL 폴백: 로컬 파일 없을 때 원본 URL로 표시
    media_url_fallback = image_for_ad(ad)

    with col_media:
        if video and video.exists():
            st.video(str(video))
        elif thumb and thumb.exists():
            st.image(str(thumb), width="stretch")
        elif media_url_fallback:
            st.image(media_url_fallback, width="stretch")
        else:
            st.info("표시할 미디어가 없습니다.")

        dl_left, dl_right = st.columns(2)
        with dl_left:
            if thumb and thumb.exists():
                st.download_button(
                    "⬇  썸네일 다운로드",
                    data=thumb.read_bytes(),
                    file_name=thumb.name,
                    mime="image/jpeg",
                    width="stretch",
                    key=f"dl_thumb_{ad_id}",
                )
            else:
                st.button("⬇  썸네일 없음", disabled=True, width="stretch", key=f"dl_thumb_na_{ad_id}")
        with dl_right:
            if video and video.exists():
                st.download_button(
                    "⬇  영상 다운로드",
                    data=video.read_bytes(),
                    file_name=video.name,
                    mime="video/mp4",
                    width="stretch",
                    key=f"dl_video_{ad_id}",
                )
            else:
                st.button("⬇  영상 없음", disabled=True, width="stretch", key=f"dl_video_na_{ad_id}")

    with col_info:
        st.markdown(f"### {page_name}")
        st.caption(f"광고 ID `{ad_id}`")

        m1, m2 = st.columns(2)
        m1.metric("게재일수", f"{int(active_days) if active_days else 0}일")
        m2.metric("상태", "활성" if is_active else "비활성")

        if start_date:
            st.markdown(f"📅  **게재 시작**  ·  {start_date}")
        if has_video:
            st.markdown("🎬  **영상 소재**")
        if cta:
            st.markdown(f"🔘  **CTA**  ·  {cta}")
        if landing:
            st.markdown(f"[🛒  랜딩페이지 열기]({landing})")
        st.markdown(f"[📺  광고 라이브러리에서 보기]({ad_library_url(ad_id)})")

        st.markdown("---")
        st.markdown("**캡션**")
        if caption:
            st.markdown(caption)
        else:
            st.caption("_(캡션 없음)_")


@st.fragment
def render_gallery(ads: list[dict], namespace: str = "main") -> None:
    if not ads:
        st.info("표시할 광고가 없습니다. 필터를 줄이거나 스크래핑을 먼저 실행하세요.")
        return

    favorites: set = st.session_state.get("favorites", set())

    for row_start in range(0, len(ads), 4):
        cols = st.columns(4)
        for offset, ad in enumerate(ads[row_start:row_start + 4]):
            with cols[offset]:
                img_src = image_for_ad(ad)
                if img_src:
                    st.image(img_src, width="stretch")
                else:
                    st.info("이미지 없음")

                ad_id = str(ad.get("ad_id") or f"{row_start}_{offset}")
                page_name = ad.get("page_name") or ad.get("page_id") or "광고"
                short_name = page_name.split(" - ")[0][:18]
                video_icon = "🎬 " if ad.get("has_video") else "🖼️ "

                fav = ad_id in favorites
                heart_col, detail_col = st.columns([1, 4])
                with heart_col:
                    if st.button(
                        "❤️" if fav else "🤍",
                        key=f"fav_btn_{namespace}_{ad_id}",
                        width="stretch",
                        help="찜하기 / 찜 해제",
                    ):
                        new_state = db.toggle_favorite(ad_id)
                        if new_state:
                            favorites.add(ad_id)
                        else:
                            favorites.discard(ad_id)
                        st.session_state.favorites = favorites
                        # 찜한 소재 탭도 같이 갱신되도록 항상 전체 rerun
                        st.rerun(scope="app")
                with detail_col:
                    if st.button(
                        f"{video_icon}{short_name}  ▸  상세",
                        key=f"detail_btn_{namespace}_{ad_id}",
                        width="stretch",
                        help="클릭하면 영상 재생·캡션·다운로드가 열립니다",
                    ):
                        show_ad_detail(ad)


competitors = db.list_competitors(only_active=False)
config = load_config()
competitor_options = {
    f"{c['page_name']} ({c['page_id']})": c["page_id"] for c in competitors
}

if "favorites" not in st.session_state:
    st.session_state.favorites = db.get_all_favorite_ids()

with st.sidebar:
    st.markdown(
        '<p class="sidebar-title">META 광고 레퍼런스 수집</p>',
        unsafe_allow_html=True,
    )

    selected_label = st.selectbox("경쟁사", list(competitor_options.keys()))
    selected_page_id = competitor_options[selected_label]

    with st.expander("🗂️ 경쟁사 관리"):
        for c in competitors:
            col_name, col_btn = st.columns([3, 1])
            with col_name:
                st.caption(c["page_name"] or c["page_id"])
            with col_btn:
                if st.button(
                    "🗑️",
                    key=f"del_comp_{c['page_id']}",
                    help=f"{c['page_name']} 삭제",
                    width="stretch",
                ):
                    confirm_delete_competitor(str(c["page_id"]), c["page_name"] or str(c["page_id"]))

    with st.expander("➕ 경쟁사 추가"):
        new_url = st.text_input(
            "광고 라이브러리 URL 또는 페이지 ID",
            key="new_comp_url",
            placeholder="https://www.facebook.com/ads/library/?view_all_page_id=...",
        )
        new_name = st.text_input(
            "경쟁사 이름 (선택)",
            key="new_comp_name",
            placeholder="예: 클래스101",
        )
        if st.button("추가 + 수집 시작", key="add_comp_btn", type="primary", width="stretch"):
            url_val = new_url.strip()
            if not url_val:
                st.error("URL 또는 페이지 ID를 입력해주세요.")
            else:
                cmd = [sys.executable, str(ROOT / "scraper" / "main.py"), "--url", url_val]
                if new_name.strip():
                    cmd += ["--name", new_name.strip()]
                run_collect_dialog(cmd)

    # ── ⚡ 지금 수집 (스케줄러를 기다리지 않고 현재 기준으로 즉시 일괄 수집) ──
    st.markdown("---")
    collect_scope = st.radio(
        "수집 범위",
        ["선택 경쟁사만", "전체 경쟁사"],
        horizontal=True,
        key="collect_scope",
    )
    if st.button("⚡  지금 수집", key="collect_now_btn", type="primary", width="stretch"):
        cmd = [sys.executable, str(ROOT / "scraper" / "main.py")]
        if collect_scope == "선택 경쟁사만" and selected_page_id:
            cmd += ["--page-id", str(selected_page_id)]
        run_collect_dialog(cmd)
    st.caption("⚠️ 봇 차단 방지를 위해 너무 자주 누르지 마세요. 휴식·차단 감지 로직은 그대로 동작합니다.")

    raw_ads = load_ads_for_page(selected_page_id)
    raw_df = to_frame(raw_ads)

    st.markdown("---")
    st.markdown("**필터**")

    if not raw_df.empty and raw_df["start_date"].notna().any():
        min_day = raw_df["start_date"].min().date()
        max_day = raw_df["start_date"].max().date()
        picked_range = st.date_input("게재기간", value=(min_day, max_day))
        if isinstance(picked_range, tuple) and len(picked_range) == 2:
            start_day, end_day = picked_range
        else:
            start_day, end_day = None, None
    else:
        start_day, end_day = None, None
        st.caption("게재일 데이터가 아직 없습니다.")

    active_filter = st.radio("활성화", ["전체", "활성만", "비활성만"], horizontal=True)
    media_filter = st.radio("소재 유형", ["전체", "이미지", "영상"], horizontal=True)
    min_active_days = st.slider("최소 게재일", 0, 60, 0)

    st.markdown("---")
    db_url = notion_db_url(config)
    if db_url:
        st.link_button(
            "📂  광고 DB 열기  ↗",
            db_url,
            width="stretch",
            type="primary",
        )
        st.caption('클로드 코드에게 "노션에 올려줘" 라고 말하면 자동 정리됩니다')
    else:
        st.caption("노션 연동 미설정 — config.json의 notion 섹션을 채워주세요.")

    last_runs = db.last_run_summary()
    if last_runs:
        st.markdown("---")
        st.markdown("**최근 수집**")
        for run in last_runs[:6]:
            st.caption(f"{run.get('page_id')}: {str(run.get('last_run', ''))[:16]}")

filtered_ads = apply_filters(
    raw_ads,
    start_day,
    end_day,
    active_filter,
    media_filter,
    min_active_days,
)
filtered_df = to_frame(filtered_ads)

render_metrics(filtered_ads)
st.divider()

gallery_header, fav_header, table_header = st.tabs(["이미지 레퍼런스", "💖 찜한 소재", "데이터 테이블"])

with gallery_header:
    render_gallery(filtered_ads, namespace="main")

with fav_header:
    fav_ads = db.winner_candidates()
    if not fav_ads:
        st.info("아직 찜한 소재가 없어요. 카드에서 🤍를 눌러 찜해보세요.")
    else:
        st.caption(f"총 {len(fav_ads)}개")
        fav_zip_bytes, fav_zip_count = build_media_zip(fav_ads)
        st.download_button(
            f"⬇️  찜한 소재 일괄 다운로드 ({fav_zip_count}개 파일)",
            data=fav_zip_bytes or b"",
            file_name="ad_favorites_media.zip",
            mime="application/zip",
            disabled=fav_zip_bytes is None,
            width="stretch",
            type="primary",
            key="fav_media_download",
        )
        render_gallery(fav_ads, namespace="favs")

with table_header:
    if filtered_df.empty:
        st.info("표시할 데이터가 없습니다.")
    else:
        table = filtered_df[
            [
                "page_name",
                "start_date",
                "active_days",
                "is_active",
                "has_video",
                "caption",
                "ad_id",
            ]
        ].copy()
        table["start_date"] = table["start_date"].dt.date.astype("string")
        table["media_files"] = [
            len(media_files_for_ad(ad)) for ad in filtered_ads
        ]
        table["광고 보기"] = [
            ad_library_url(str(ad.get("ad_id") or "")) for ad in filtered_ads
        ]
        table["랜딩 URL"] = [ad.get("landing_url") or "" for ad in filtered_ads]
        table = table.rename(
            columns={
                "page_name": "경쟁사",
                "start_date": "게재일",
                "active_days": "게재일수",
                "is_active": "활성",
                "has_video": "영상",
                "caption": "캡션",
                "ad_id": "광고 ID",
                "media_files": "소재 파일 수",
            }
        )
        st.dataframe(
            table,
            width="stretch",
            height=420,
            column_config={
                "광고 보기": st.column_config.LinkColumn(
                    "광고 보기",
                    help="페이스북 광고 라이브러리에서 원본 이미지·영상 바로 보기",
                    display_text="🔗 라이브러리 열기",
                ),
                "랜딩 URL": st.column_config.LinkColumn(
                    "랜딩 URL",
                    help="광고가 가리키는 랜딩 페이지 새 탭에서 열기",
                    display_text="🛒 랜딩 열기",
                ),
            },
        )

        table_zip_bytes, table_zip_count = build_media_zip(filtered_ads)
        st.download_button(
            f"⬇️  전체 소재 일괄 다운로드 ({table_zip_count}개 파일)",
            data=table_zip_bytes or b"",
            file_name="ad_reference_media.zip",
            mime="application/zip",
            disabled=table_zip_bytes is None,
            width="stretch",
            type="primary",
            key="table_media_download",
        )
