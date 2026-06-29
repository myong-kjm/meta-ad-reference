"""Playwright 브라우저 세팅 — 봇 회피 핵심.

전략:
1. headless=False (실제 창 띄움)
2. playwright-stealth 적용
3. 본인 Chrome 프로필 재사용 (이미 로그인된 세션)
4. 한국어/한국 로케일 강제
"""
from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

from playwright.sync_api import BrowserContext, Playwright

try:
    from playwright_stealth import Stealth  # type: ignore
    HAS_STEALTH = True
except ImportError:
    HAS_STEALTH = False


def launch_context(playwright: Playwright, config: dict) -> BrowserContext:
    """봇 회피 설정 적용한 BrowserContext 반환.

    config 키:
      - use_my_chrome_profile (bool)
      - chrome_profile_path (str, expanduser 적용 전)
      - chrome_profile_name (str, 보통 "Default")
      - headless (bool)
    """
    use_profile = bool(config.get("use_my_chrome_profile", True))
    headless = bool(config.get("headless", False))

    common_args = [
        "--disable-blink-features=AutomationControlled",
        "--no-default-browser-check",
        "--disable-features=IsolateOrigins,site-per-process",
        "--lang=ko-KR",
    ]
    common_kwargs: dict[str, Any] = {
        "headless": headless,
        "args": common_args,
        "locale": "ko-KR",
        "timezone_id": "Asia/Seoul",
        "viewport": {"width": 1440, "height": 900},
        "user_agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/132.0.0.0 Safari/537.36"
        ),
    }

    if use_profile:
        chrome_root = Path(os.path.expanduser(
            config.get("chrome_profile_path", "~/Library/Application Support/Google/Chrome")
        ))
        profile_name = config.get("chrome_profile_name", "Default")
        src_profile = chrome_root / profile_name

        if not src_profile.exists():
            print(f"⚠️  Chrome 프로필 못 찾음: {src_profile}")
            print("   → 일반 모드로 폴백 (로그인 안 된 새 세션)")
            use_profile = False
        else:
            # 안전을 위해 본인 프로필을 직접 안 쓰고 임시 복사본을 씀
            # (Chrome이 동시에 같은 프로필을 잠그면 충돌)
            tmp_profile = Path(tempfile.gettempdir()) / "ad-scraper-profile"
            if not tmp_profile.exists():
                print(f"📋 본인 Chrome 프로필을 임시 위치로 복사 중... ({src_profile.name})")
                # 첫 실행만 복사. 두 번째부터는 기존 복사본 재사용 (캐시/쿠키 유지)
                _safe_copy_profile(src_profile, tmp_profile)
            context = playwright.chromium.launch_persistent_context(
                user_data_dir=str(tmp_profile),
                channel="chrome",  # 실제 Chrome 사용 (Chromium 아님)
                **common_kwargs,
            )
            _apply_stealth_to_context(context)
            return context

    # 폴백: 일반 launch
    browser = playwright.chromium.launch(headless=headless, args=common_args)
    context = browser.new_context(
        locale="ko-KR",
        timezone_id="Asia/Seoul",
        viewport={"width": 1440, "height": 900},
        user_agent=common_kwargs["user_agent"],
    )
    _apply_stealth_to_context(context)
    return context


def _safe_copy_profile(src: Path, dst: Path) -> None:
    """Chrome 프로필 임시 복사 — 잠금 파일이나 캐시 일부는 건너뜀."""
    ignore = shutil.ignore_patterns(
        "Singleton*", "lockfile", "*.lock",
        "Cache*", "Code Cache*", "GPUCache",
        "Service Worker", "ShaderCache",
    )
    shutil.copytree(src, dst, ignore=ignore, dirs_exist_ok=False)


def _apply_stealth_to_context(context: BrowserContext) -> None:
    if not HAS_STEALTH:
        # stealth 없어도 작동은 함. 단, 봇 감지 확률 좀 올라감
        print("ℹ️  playwright-stealth 미설치. webdriver 흔적만 직접 제거합니다.")
        context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
        )
        return
    # playwright-stealth 2.x — Stealth 인스턴스의 init script를 컨텍스트에 주입
    try:
        stealth = Stealth()
        stealth.apply_stealth_sync(context)
    except Exception as e:
        print(f"ℹ️  stealth 적용 실패 ({e}). webdriver 흔적만 직접 제거합니다.")
        context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
        )
