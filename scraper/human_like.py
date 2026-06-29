"""봇 회피 — 사람형 행동 시뮬레이션 유틸.

핵심 원칙:
- 절대 0초로 즉시 행동 X
- 스크롤은 부드럽게, 가끔 위로
- 마우스는 페이지 진입 후 한 번 움직여줌
"""
from __future__ import annotations

import random
import time
from playwright.sync_api import Page


def sleep(min_s: float, max_s: float) -> None:
    """랜덤 sleep. 사람 반응 시간 모사."""
    time.sleep(random.uniform(min_s, max_s))


def wiggle_mouse(page: Page) -> None:
    """페이지 진입 후 마우스를 자연스러운 위치로 이동."""
    try:
        viewport = page.viewport_size or {"width": 1280, "height": 800}
        x = random.randint(100, viewport["width"] - 100)
        y = random.randint(100, viewport["height"] - 100)
        page.mouse.move(x, y, steps=random.randint(10, 25))
    except Exception:
        pass


def smooth_scroll(page: Page, target_pixels: int = 800) -> None:
    """부드럽게 N픽셀 스크롤. JS window.scrollBy 사용 (마우스 위치 무관하게 동작)."""
    chunks = random.randint(4, 8)
    chunk_size = target_pixels // chunks
    for _ in range(chunks):
        delta = chunk_size + random.randint(-30, 30)
        try:
            page.evaluate(f"window.scrollBy(0, {delta})")
        except Exception:
            page.mouse.wheel(0, delta)
        time.sleep(random.uniform(0.2, 0.4))


def occasional_scroll_back(page: Page) -> None:
    """가끔 위로 스크롤. 사람이 놓친 거 다시 보는 패턴."""
    if random.random() < 0.15:  # 15% 확률
        delta = -random.randint(200, 400)
        try:
            page.evaluate(f"window.scrollBy(0, {delta})")
        except Exception:
            page.mouse.wheel(0, delta)
        time.sleep(random.uniform(0.5, 1.2))


def page_load_pause() -> None:
    """페이지 로드 후 사람이 화면 훑는 시간."""
    sleep(3.0, 7.0)


def between_actions_pause() -> None:
    """클릭/입력 사이 짧은 호흡."""
    sleep(0.5, 1.5)


def between_pages_pause(min_s: int, max_s: int) -> None:
    """경쟁사 페이지 간 긴 휴식."""
    delay = random.uniform(min_s, max_s)
    print(f"  → 다음 페이지까지 {delay:.0f}초 휴식 (봇 감지 회피)")
    time.sleep(delay)
