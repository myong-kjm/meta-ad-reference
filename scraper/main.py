"""광고 라이브러리 자동 스크래퍼 — 메인 진입점.

흐름:
1. config.json 읽기 → 경쟁사 목록
2. 각 경쟁사마다:
   a. URL 빌드 (relevancy_monthly_grouped 모드 = 신규/관련도순)
   b. Playwright로 페이지 열기 + 스크롤
   c. GraphQL 응답 가로채기 → extractor로 광고 객체 만들기
   d. 미디어 다운로드
   e. SQLite에 upsert
3. 경쟁사 간 30~60초 휴식 (봇 회피)
4. 봇 차단 감지 시 즉시 중단 (재시도 안 함)

⚠️ 매일 1회만 실행. 더 자주 돌리지 마세요.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

# Windows CP949 터미널에서 이모지/한글 출력 오류 방지
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from playwright.sync_api import Page, TimeoutError as PWTimeout, sync_playwright

# 상위 폴더에서 import
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scraper import db, human_like, notion_sync
from scraper.browser import launch_context
from scraper.extractor import extract_ads_from_graphql
from scraper.media_download import download_media
from scraper.url_builder import page_url, parse_page_id

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config.json"
CONFIG_EXAMPLE = ROOT / "config.example.json"
LOG_DIR = ROOT / "data" / "logs"


# 차단 감지 키워드들 (페이지 본문에서 발견하면 즉시 중단)
BLOCK_INDICATORS = [
    "You must log in to continue",
    "로그인해야 계속할 수 있습니다",
    "Please verify you're a human",
    "Suspicious activity",
    "checkpoint",
    "Temporarily blocked",
]


class BlockedError(RuntimeError):
    """봇 감지 / 차단 감지 시 발생."""


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        print(f"❌ config.json이 없습니다. config.example.json을 복사해서 만들고 경쟁사를 채워주세요.")
        print(f"   cp {CONFIG_EXAMPLE} {CONFIG_PATH}")
        sys.exit(1)
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def _is_placeholder_name(name: str, page_id: str) -> bool:
    """아직 실제 페이지명으로 해석되지 않은 임시 이름인지."""
    name = (name or "").strip()
    return (not name) or name == str(page_id) or name.startswith("페이지 ")


def load_competitors(config: dict) -> list[dict]:
    """config.json + DB(competitors) 병합. 같은 page_id면 '해석된' 이름을 우선 보존.

    대시보드에서 추가한 경쟁사는 DB에만 있고 config.json엔 없을 수 있으므로,
    둘을 합쳐야 스케줄러/즉시수집이 모두 같은 목록을 본다.
    """
    merged: dict[str, dict] = {}
    for c in config.get("competitors", []):
        pid = str(c["page_id"])
        merged[pid] = {
            "page_id": pid,
            "page_name": c.get("page_name", pid),
            "notes": c.get("notes", ""),
        }
    try:
        for row in db.list_competitors(only_active=False):
            pid = str(row["page_id"])
            db_name = row["page_name"]
            if pid in merged:
                # DB에 플레이스홀더가 아닌 실제 이름이 있으면 그걸 사용
                if not _is_placeholder_name(db_name, pid):
                    merged[pid]["page_name"] = db_name
            else:
                merged[pid] = {
                    "page_id": pid,
                    "page_name": db_name or pid,
                    "notes": row["notes"] or "",
                }
    except Exception:
        pass
    return list(merged.values())


def _resolve_page_name(cards: list[dict]) -> str | None:
    """수집한 광고들에서 실제 페이지명(예: '무신사')을 추려낸다."""
    from collections import Counter

    names = [str(c.get("page_name")).strip() for c in cards if c.get("page_name")]
    names = [n for n in names if n]
    if not names:
        return None
    return Counter(names).most_common(1)[0][0]


def _update_config_name(page_id: str, name: str) -> None:
    """config.json에 그 page_id가 있고 임시 이름이면 실제 이름으로 갱신."""
    try:
        cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return
    changed = False
    for c in cfg.get("competitors", []):
        if str(c.get("page_id")) == str(page_id) and _is_placeholder_name(c.get("page_name", ""), page_id):
            c["page_name"] = name
            changed = True
    if changed:
        CONFIG_PATH.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")


def _extract_from_page_script(page: Page) -> list[dict]:
    """페이지 script 태그의 __bbox 임베디드 JSON에서 광고 데이터 추출.

    GraphQL API가 rate limit에 걸려도 SSR HTML에 동일 데이터가 임베딩됨.
    JS로 script 태그를 스캔해 {"data":{"ad_library_main":...}} 블록을 추출한다.
    """
    try:
        payload = page.evaluate("""
            () => {
                for (const script of document.querySelectorAll('script')) {
                    const text = script.textContent;
                    if (!text.includes('"ad_archive_id"')) continue;

                    // "data":{ 패턴으로 data 오브젝트 시작 위치 탐색
                    // Facebook SSR 구조: __bbox > result > "data":{...}
                    const adIdx = text.lastIndexOf('"ad_archive_id"');
                    if (adIdx === -1) continue;
                    const kwPos = text.lastIndexOf('"data":{', adIdx);
                    if (kwPos === -1) continue;
                    const dataStart = kwPos + 7; // '{'의 위치

                    // 괄호 카운터로 JSON 블록 끝 찾기
                    let depth = 0, inStr = false, esc = false, end = -1;
                    const limit = Math.min(text.length, dataStart + 5000000);
                    for (let i = dataStart; i < limit; i++) {
                        const ch = text[i];
                        if (esc) { esc = false; continue; }
                        if (inStr) {
                            if (ch === '\\\\') esc = true;
                            else if (ch === '"') inStr = false;
                            continue;
                        }
                        if (ch === '"') { inStr = true; continue; }
                        if (ch === '{') depth++;
                        else if (ch === '}') { if (--depth === 0) { end = i + 1; break; } }
                    }

                    if (end > dataStart) {
                        try { return JSON.parse(text.slice(dataStart, end)); } catch(e) {}
                    }
                }
                return null;
            }
        """)
        if payload and isinstance(payload, dict):
            return [payload]
    except Exception as e:
        print(f"    ⚠️  HTML 폴백 추출 오류: {e}")
    return []


def check_for_block(page: Page) -> None:
    """페이지 본문에 차단 메시지가 있는지 검사."""
    try:
        body = page.locator("body").inner_text(timeout=3000)
        for keyword in BLOCK_INDICATORS:
            if keyword.lower() in body.lower():
                raise BlockedError(f"차단 키워드 감지: '{keyword}'")
    except PWTimeout:
        pass


def scrape_page(page: Page, page_id: str, page_name: str,
                max_ads: int, max_scrolls: int, mode: str) -> list[dict]:
    """경쟁사 한 페이지 스크래핑."""
    target_url = page_url(page_id, mode=mode)
    print(f"  → 열기: {target_url[:90]}...")

    collected_payloads: list[dict] = []

    def on_response(response):
        url = response.url
        url_lower = url.lower()
        # Facebook GraphQL / API 엔드포인트
        if not ("graphql" in url_lower or
                ("/api/" in url_lower and "facebook.com" in url_lower)):
            return
        if not response.ok:
            return
        try:
            # response.body()가 response.text()보다 이벤트 핸들러 안에서 안정적
            text = response.body().decode("utf-8", errors="replace")
        except Exception:
            return
        # for(;;); 프리픽스 제거 — 이게 있으면 멀티라인 JSON을 라인별로 파싱해도 실패함
        stripped = text.lstrip()
        if stripped.startswith("for (;;);"):
            text = stripped[len("for (;;);"):]
        if not text:
            return
        # 광고 라이브러리 응답 여부 확인 (adArchiveId 소문자 d 포함)
        if not any(m in text for m in ("ad_archive_id", "adArchiveID", "adArchiveId")):
            return
        # JSON 파싱: 전체 시도 → 실패 시 라인별 시도 (multi-JSON 대응)
        try:
            collected_payloads.append(json.loads(text))
            return
        except json.JSONDecodeError:
            pass
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                collected_payloads.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    page.on("response", on_response)

    try:
        page.goto(target_url, wait_until="domcontentloaded", timeout=45000)
    except PWTimeout:
        print(f"    ⚠️  페이지 로드 타임아웃 — 부분 데이터로 진행")

    human_like.page_load_pause()
    human_like.wiggle_mouse(page)

    check_for_block(page)

    # 광고 GraphQL 응답이 늦게 도착하는 경우 대비 — 첫 광고 payload가 잡힐 때까지 최대 ~18초 대기.
    # (스크롤·추출이 먼저 끝나서 '0개'로 오판하던 문제 방지)
    waited = 0.0
    while waited < 18.0:
        if any(extract_ads_from_graphql(p) for p in collected_payloads):
            break
        page.wait_for_timeout(1500)
        waited += 1.5
    else:
        print(f"    ⚠️  18초간 GraphQL 응답 없음 — HTML 임베디드 데이터로 폴백 시도")
        html_payloads = _extract_from_page_script(page)
        if html_payloads:
            print(f"    ✓ HTML에서 광고 데이터 추출 성공 ({len(html_payloads)}개 블록)")
            collected_payloads.extend(html_payloads)
        else:
            print("       → HTML에서도 데이터 없음 (봇 차단 또는 로그인 필요)")

    print(f"    → 데이터 {len(collected_payloads)}건, 스크롤 시작")
    # 스크롤로 광고 더 로드
    for i in range(max_scrolls):
        human_like.smooth_scroll(page, target_pixels=1200)
        human_like.between_actions_pause()
        human_like.occasional_scroll_back(page)

        # 충분히 모았으면 중단
        cards: list[dict] = []
        for p in collected_payloads:
            cards.extend(extract_ads_from_graphql(p))
        unique_ids = {c.get("ad_id") for c in cards if c.get("ad_id")}
        if len(unique_ids) >= max_ads:
            print(f"    ✓ {len(unique_ids)}개 모음 (목표 {max_ads}개 달성)")
            break

        if i % 5 == 4:
            check_for_block(page)

    # 최종 추출
    all_cards: list[dict] = []
    seen_ids: set[str] = set()
    for p in collected_payloads:
        for card in extract_ads_from_graphql(p):
            aid = card.get("ad_id")
            if aid and aid not in seen_ids:
                seen_ids.add(aid)
                # 페이지명 보강 (snapshot에 없는 경우)
                if not card.get("page_name"):
                    card["page_name"] = page_name
                if not card.get("page_id"):
                    card["page_id"] = page_id
                all_cards.append(card)
            if len(all_cards) >= max_ads:
                break
        if len(all_cards) >= max_ads:
            break

    page.remove_listener("response", on_response)
    return all_cards


def process_page(page: Page, competitor: dict, config: dict, mode: str) -> tuple[int, int, str]:
    """경쟁사 한 곳 처리. Returns (ads_found, ads_new, status)."""
    page_id = str(competitor["page_id"])
    page_name = competitor.get("page_name", page_id)
    max_ads = int(config.get("max_ads_per_page", 30))
    max_scrolls = int(config.get("max_scroll_attempts", 20))

    started = datetime.now()
    try:
        cards = scrape_page(page, page_id, page_name, max_ads, max_scrolls, mode)
        # 0건이면 일시적 throttle 의심 → 1회만 쿨다운 후 재시도 (밴이 아니라 빈 응답일 때 회복)
        if not cards:
            cooldown = int(config.get("empty_retry_cooldown_sec", 45))
            print(f"    ⚠️  광고 0건 — 일시 제한(throttle) 의심. {cooldown}초 쉬고 1회 재시도")
            time.sleep(cooldown)
            human_like.wiggle_mouse(page)
            cards = scrape_page(page, page_id, page_name, max_ads, max_scrolls, mode)
    except BlockedError as e:
        db.log_run(page_id, mode, 0, 0, started, status="blocked", error=str(e))
        raise
    except Exception as e:
        db.log_run(page_id, mode, 0, 0, started, status="error", error=str(e))
        raise

    # 재시도 후에도 0건이면 'empty' 상태로 구분 기록 (정상 ok 아님 — throttle/빈결과 추적용)
    if not cards:
        db.log_run(page_id, mode, 0, 0, started, status="empty",
                   error="광고 0건 (재시도 후) — 일시 제한/빈 결과 가능성")
        print(f"    ⚠️  재시도 후에도 0건 — 'empty'로 기록 (밴 아님, 잠시 후 다시 시도 권장)")
        return 0, 0, "empty"

    # 실제 페이지명 자동 해석: 임시 이름('페이지 123…')이면 수집된 광고에서 진짜 이름으로 교체
    real_name = _resolve_page_name(cards)
    if real_name and _is_placeholder_name(page_name, page_id):
        try:
            db.set_competitor_name(page_id, real_name)
            _update_config_name(page_id, real_name)
            print(f"    ↳ 경쟁사 이름 해석: '{page_name}' → '{real_name}'")
            page_name = real_name
        except Exception as e:
            print(f"    ⚠️  이름 해석 갱신 실패: {e}")

    new_count = 0
    saved_cards: list[dict] = []
    for card in cards:
        if not card.get("ad_id"):
            continue
        card["media_paths"] = []

        was_new, _ = db.upsert_ad(card)
        saved_cards.append(card)
        if was_new:
            new_count += 1

    # 노션 자동 적재 (환경변수 있을 때만)
    if notion_sync.is_enabled() and saved_cards:
        print(f"  → 노션 적재 시작 ({len(saved_cards)}개)")
        try:
            res = notion_sync.sync_ads(saved_cards)
            print(f"    ✓ 노션: 신규 {res['new']} / 업데이트 {res['updated']} / 실패 {res['errors']}")
        except Exception as e:
            print(f"    ⚠️  노션 적재 전체 실패: {e}")

    db.log_run(page_id, mode, len(cards), new_count, started)
    return len(cards), new_count, "ok"


def register_competitor(raw_url_or_id: str, name: str | None = None) -> str:
    """터미널에서 받은 URL(또는 페이지 ID)로 신규 경쟁사를 등록.

    - URL에서 view_all_page_id 숫자를 자동 추출
    - DB(competitors)에 upsert + config.json competitors에도 추가(없을 때만)
    Returns: 등록된 page_id. 파싱 실패 시 종료.
    """
    page_id = parse_page_id(raw_url_or_id)
    if not page_id:
        print("❌ URL/입력에서 페이지 ID를 찾지 못했습니다.")
        print("   `view_all_page_id=…`가 들어간 광고 라이브러리 URL이거나 페이지 ID 숫자를 넣어주세요.")
        sys.exit(1)

    display_name = (name or "").strip() or f"페이지 {page_id}"
    db.init_db()
    db.upsert_competitor(page_id, display_name, "")

    # config.json에도 추가(있으면 그대로 둠) — 스케줄러가 보는 목록에 영구 반영
    try:
        cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8")) if CONFIG_PATH.exists() else {}
        comps = cfg.setdefault("competitors", [])
        if not any(str(c.get("page_id")) == page_id for c in comps):
            comps.append({"page_id": page_id, "page_name": display_name, "notes": ""})
            CONFIG_PATH.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        print(f"⚠️  config.json 갱신 실패(무시하고 진행): {e}")

    print(f"➕ 경쟁사 등록: {display_name} (page_id={page_id})")
    return page_id


def run_all(mode: str = "relevancy_monthly_grouped", only_page_id: str | None = None,
            headless: bool | None = None) -> None:
    config = load_config()
    # --headless 같은 CLI 오버라이드: config의 headless 값을 덮어쓴다
    if headless is not None:
        config["headless"] = bool(headless)
    db.init_db()

    competitors = load_competitors(config)

    if only_page_id:
        only_page_id = str(only_page_id)
        competitors = [c for c in competitors if str(c["page_id"]) == only_page_id]
        if not competitors:
            print(f"❌ page_id={only_page_id} 경쟁사를 config.json/DB에서 찾지 못했습니다.")
            sys.exit(1)

    if not competitors:
        print("❌ 수집할 경쟁사가 없습니다. (config.json 또는 대시보드에서 추가하세요)")
        sys.exit(1)

    # competitors 테이블에도 동기화 (병합된 이름 그대로 — 해석된 이름 보존)
    for c in competitors:
        db.upsert_competitor(
            str(c["page_id"]),
            c.get("page_name", str(c["page_id"])),
            c.get("notes", ""),
        )

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOG_DIR / f"{datetime.now().date().isoformat()}.log"

    print(f"🚀 스크래핑 시작 — {len(competitors)}개 경쟁사, 모드={mode}")
    print(f"   로그: {log_path}")

    with sync_playwright() as p:
        context = launch_context(p, config)
        page = context.new_page()

        total_found, total_new = 0, 0

        try:
            for i, competitor in enumerate(competitors, 1):
                page_name = competitor.get("page_name", competitor["page_id"])
                print(f"\n[{i}/{len(competitors)}] {page_name}")

                try:
                    found, new, _ = process_page(page, competitor, config, mode)
                    total_found += found
                    total_new += new
                    print(f"    ✓ 광고 {found}개 (신규 {new}개)")
                except BlockedError as e:
                    print(f"\n🛑 봇 차단 감지: {e}")
                    print("   → 즉시 중단. 24시간 후 재시도 권장.")
                    break
                except Exception as e:
                    print(f"    ❌ 실패: {e}")
                    traceback.print_exc()
                    # 한 페이지 실패해도 다음 페이지는 계속
                    continue

                # 다음 페이지 가기 전 휴식 (마지막 페이지는 휴식 X)
                if i < len(competitors):
                    human_like.between_pages_pause(
                        int(config.get("between_page_delay_min", 30)),
                        int(config.get("between_page_delay_max", 60)),
                    )

        finally:
            try:
                context.close()
            except Exception:
                pass

    print(f"\n✅ 완료 — 광고 {total_found}개 수집 (신규 {total_new}개)")


def main():
    parser = argparse.ArgumentParser(description="페이스북 광고 라이브러리 자동 수집기")
    parser.add_argument(
        "--mode",
        choices=["relevancy_monthly_grouped", "total_impressions", "both"],
        default="relevancy_monthly_grouped",
        help="정렬 모드. 'both'는 두 모드를 순차 실행",
    )
    parser.add_argument(
        "--page-id",
        default=None,
        help="이 page_id 경쟁사 하나만 즉시 수집. 생략 시 전체",
    )
    parser.add_argument(
        "--url",
        default=None,
        help="신규 경쟁사 추가 + 즉시 수집. 광고 라이브러리 URL(또는 페이지 ID 숫자)을 그대로 넣으세요.",
    )
    parser.add_argument(
        "--name",
        default=None,
        help="--url로 추가하는 경쟁사 표시 이름 (생략 시 페이지 ID로 표시 후 자동 해석)",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="창을 띄우지 않고 백그라운드(headless)로 수집. (config의 headless 값을 덮어씀)",
    )
    args = parser.parse_args()

    # --headless 플래그가 있으면 True, 없으면 None(=config 값 사용)
    headless = True if args.headless else None

    # --url: 터미널에서 신규 경쟁사 직접 추가 → 그 경쟁사만 수집
    only_page_id = args.page_id
    if args.url:
        only_page_id = register_competitor(args.url, args.name)

    if args.mode == "both":
        print("🔄 모드 1/2: relevancy_monthly_grouped (신규/관련도순)")
        run_all("relevancy_monthly_grouped", only_page_id=only_page_id, headless=headless)
        print("\n🔄 모드 2/2: total_impressions (노출수순)")
        run_all("total_impressions", only_page_id=only_page_id, headless=headless)
    else:
        run_all(args.mode, only_page_id=only_page_id, headless=headless)


if __name__ == "__main__":
    main()
