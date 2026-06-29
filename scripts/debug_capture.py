"""진단용 — 광고 라이브러리 페이지에서 실제로 어떤 네트워크 요청이 가는지 본다.

스크래퍼가 광고 0개를 뽑은 원인 추적용.
"""
import sys
import time
from pathlib import Path
from collections import Counter

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from playwright.sync_api import sync_playwright
from scraper.url_builder import page_url

URL = page_url("1947160905536967", mode="relevancy_monthly_grouped")
print(f"테스트 URL: {URL}\n")

response_urls = []
response_with_ads = []

def on_response(response):
    url = response.url
    response_urls.append(url)
    if "graphql" in url.lower() or "ads" in url.lower():
        try:
            text = response.text()
            if "ad_archive_id" in text or "adArchiveID" in text or "page_id" in text:
                response_with_ads.append({
                    "url": url[:120],
                    "len": len(text),
                    "preview": text[:200],
                })
        except Exception:
            pass

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, args=[
        "--disable-blink-features=AutomationControlled",
        "--lang=ko-KR",
    ])
    context = browser.new_context(
        locale="ko-KR",
        timezone_id="Asia/Seoul",
        viewport={"width": 1440, "height": 900},
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36",
    )
    page = context.new_page()
    page.on("response", on_response)

    print("페이지 로드 중...")
    page.goto(URL, wait_until="domcontentloaded", timeout=45000)
    time.sleep(5)

    print(f"\n초기 로드 후 응답 수: {len(response_urls)}")
    print(f"현재 URL: {page.url}")
    title = page.title()
    print(f"페이지 타이틀: {title}")

    # 본문에서 차단 키워드 검사
    try:
        body_text = page.locator("body").inner_text(timeout=3000)
        print(f"본문 처음 300자: {body_text[:300]}")
    except Exception as e:
        print(f"본문 못 읽음: {e}")

    print("\n스크롤 5회 시도...")
    for i in range(5):
        page.mouse.wheel(0, 1200)
        time.sleep(2)

    print(f"\n총 응답 수: {len(response_urls)}")

    # 도메인별 집계
    from urllib.parse import urlparse
    domains = Counter(urlparse(u).netloc for u in response_urls)
    print("\n--- 도메인별 응답 수 (상위 10) ---")
    for d, c in domains.most_common(10):
        print(f"  {c:4d}  {d}")

    # 'graphql' 들어간 URL
    graphql_urls = [u for u in response_urls if "graphql" in u.lower()]
    print(f"\n--- 'graphql' 포함 URL: {len(graphql_urls)}개 ---")
    for u in graphql_urls[:5]:
        print(f"  {u[:140]}")

    # ad_archive_id 들어간 응답
    print(f"\n--- ad_archive_id 포함 응답: {len(response_with_ads)}개 ---")
    for r in response_with_ads[:3]:
        print(f"  URL: {r['url']}")
        print(f"  크기: {r['len']} 바이트")
        print(f"  미리보기: {r['preview']}")
        print()

    # 스크린샷 저장
    screenshot_path = Path(__file__).resolve().parent.parent / "data" / "debug_screenshot.png"
    page.screenshot(path=str(screenshot_path), full_page=False)
    print(f"\n스크린샷 저장: {screenshot_path}")

    time.sleep(3)
    context.close()
    browser.close()
