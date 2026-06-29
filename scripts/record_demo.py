"""Streamlit 대시보드를 자동 조작하면서 데모 영상 두 개를 녹화한다.

Demo 1: 메인 화면 → 필터 조작 → 갤러리 둘러보기
Demo 2: 카드 클릭 → 상세 모달 → 영상 재생

실행:
    .venv/bin/python scripts/record_demo.py

산출물:
    week1-ad-collector/demo-01-scraper.mp4
    week1-ad-collector/demo-02-dashboard.mp4
"""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
WEEK1_ROOT = ROOT.parent  # week1-ad-collector
TMP = ROOT / "data" / "tmp-recording"
TMP.mkdir(parents=True, exist_ok=True)

VIEWPORT = {"width": 1920, "height": 1080}
URL = "http://localhost:8501/"


def convert_webm_to_mp4(webm: Path, mp4: Path) -> None:
    """ffmpeg로 webm을 1080p mp4로 변환."""
    print(f"  ↪ ffmpeg 변환: {webm.name} → {mp4.name}")
    cmd = [
        "ffmpeg", "-y", "-i", str(webm),
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        "-vf", "scale=1920:1080:flags=lanczos",
        str(mp4),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print(res.stderr[-800:])
        raise RuntimeError(f"ffmpeg 실패 (exit {res.returncode})")
    print(f"    ✓ {mp4.stat().st_size / 1024 / 1024:.1f} MB")


def record_demo1(page) -> None:
    """Demo 1 — 메인 화면, 필터 조작, 갤러리 둘러보기."""
    print("  Demo 1 — 메인 + 필터 + 갤러리")
    page.goto(URL, wait_until="domcontentloaded")
    page.wait_for_timeout(3000)  # 첫 로드 대기

    # 메인 보기 (메트릭 + 갤러리)
    page.wait_for_timeout(2000)

    # 스크롤 천천히 — 갤러리 노출
    for _ in range(3):
        page.mouse.wheel(0, 360)
        page.wait_for_timeout(500)

    # 다시 위로
    page.evaluate("window.scrollTo({top: 0, behavior: 'smooth'})")
    page.wait_for_timeout(1500)

    # 필터 조작 — "영상" 라디오 클릭 시도
    try:
        page.get_by_text("영상", exact=True).first.click(timeout=2000)
        page.wait_for_timeout(2500)
    except Exception as e:
        print(f"    필터 영상 클릭 실패: {e}")

    # 다시 전체로
    try:
        page.get_by_text("전체", exact=True).first.click(timeout=2000)
        page.wait_for_timeout(1500)
    except Exception:
        pass

    # 갤러리 스크롤
    for _ in range(4):
        page.mouse.wheel(0, 400)
        page.wait_for_timeout(700)

    page.wait_for_timeout(1500)


def record_demo2(page) -> None:
    """Demo 2 — 카드 클릭 → 모달 → 영상 재생."""
    print("  Demo 2 — 카드 → 모달 → 영상")
    page.goto(URL, wait_until="domcontentloaded")
    page.wait_for_timeout(3500)

    # 갤러리까지 스크롤
    for _ in range(3):
        page.mouse.wheel(0, 350)
        page.wait_for_timeout(400)

    page.wait_for_timeout(1200)

    # 영상이 있는 카드의 "상세" 버튼 찾기 (🎬 표시된 버튼)
    clicked = False
    try:
        # "🎬"가 들어간 첫 번째 버튼 클릭
        page.locator("button:has-text('🎬')").first.click(timeout=4000)
        clicked = True
    except Exception as e:
        print(f"    영상 버튼 클릭 실패, 첫 카드 시도: {e}")
        try:
            page.locator("button:has-text('상세')").first.click(timeout=3000)
            clicked = True
        except Exception as e2:
            print(f"    상세 버튼도 실패: {e2}")

    if not clicked:
        print("    카드 클릭 못함 — 그냥 종료")
        page.wait_for_timeout(1000)
        return

    # 모달이 뜰 때까지 대기
    page.wait_for_timeout(2500)

    # 영상 재생 시도 — 모달 안의 video 요소 찾고 play
    try:
        page.evaluate("""
            const v = document.querySelector('[role="dialog"] video, [data-testid="stDialog"] video');
            if (v) { v.muted = true; v.play(); }
        """)
        print("    영상 재생 시작")
    except Exception as e:
        print(f"    영상 재생 실패: {e}")

    # 영상 재생되는 동안 머무름 — 9초
    page.wait_for_timeout(9000)

    # 모달 안 스크롤 (오른쪽 메타·캡션 보여주기)
    try:
        page.evaluate("""
            const dialog = document.querySelector('[role="dialog"], [data-testid="stDialog"]');
            if (dialog) dialog.scrollTop = 300;
        """)
    except Exception:
        pass
    page.wait_for_timeout(2500)

    # 닫기
    page.wait_for_timeout(1500)


def main() -> None:
    print("📹 Streamlit 대시보드 데모 녹화 시작")
    print(f"   URL: {URL}")
    print(f"   임시 폴더: {TMP}")

    with sync_playwright() as p:
        # ------ Demo 1 ------
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            viewport=VIEWPORT,
            record_video_dir=str(TMP / "demo1"),
            record_video_size=VIEWPORT,
        )
        page = ctx.new_page()
        try:
            record_demo1(page)
        finally:
            page.close()
            ctx.close()
            browser.close()

        # 가장 최근 webm 찾기
        webm1 = max((TMP / "demo1").glob("*.webm"), key=lambda p: p.stat().st_mtime)
        mp4_1 = WEEK1_ROOT / "demo-01-scraper.mp4"
        convert_webm_to_mp4(webm1, mp4_1)

        # ------ Demo 2 ------
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            viewport=VIEWPORT,
            record_video_dir=str(TMP / "demo2"),
            record_video_size=VIEWPORT,
        )
        page = ctx.new_page()
        try:
            record_demo2(page)
        finally:
            page.close()
            ctx.close()
            browser.close()

        webm2 = max((TMP / "demo2").glob("*.webm"), key=lambda p: p.stat().st_mtime)
        mp4_2 = WEEK1_ROOT / "demo-02-dashboard.mp4"
        convert_webm_to_mp4(webm2, mp4_2)

    print("✅ 녹화 완료")
    print(f"   → {mp4_1}")
    print(f"   → {mp4_2}")


if __name__ == "__main__":
    main()
