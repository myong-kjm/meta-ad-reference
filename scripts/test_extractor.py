"""[보너스 단계 전용] 인터넷·스크래핑 없이 'extractor'를 테스트하는 스크립트.

페이스북에 접속하지 않습니다. 동봉된 진짜 광고 응답 샘플 1건
(data/samples/sample_ad_response.json)을 가지고 extractor._node_to_ad 를 돌려서,
캡션·소재·게재일이 잘 뽑혔는지 ⭕/❌ 로 보여줍니다.

실행:
    python scripts/test_extractor.py

- 아직 안 만들었을 때: 거의 다 ❌  (ad_id, 페이지 이름만 ⭕)
- 보너스 단계를 완성한 뒤: 캡션·소재·게재일까지 ⭕ 로 바뀌면 성공!
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# 윈도우(한국어 cp949) 콘솔에서도 이모지·한글이 깨지지 않게 UTF-8로 출력
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scraper.extractor import _node_to_ad  # noqa: E402

SAMPLE = ROOT / "data" / "samples" / "sample_ad_response.json"


def mark(ok: bool) -> str:
    return "⭕" if ok else "❌"


def main() -> None:
    if not SAMPLE.exists():
        print(f"샘플 파일이 없어요: {SAMPLE}")
        sys.exit(1)

    payload = json.loads(SAMPLE.read_text(encoding="utf-8"))

    # 샘플은 광고 '한 건'(node)이에요. 바로 _node_to_ad 에 넣어봅니다.
    ad = _node_to_ad(payload)

    print("=" * 52)
    print("  extractor 테스트 — 샘플 광고 1건으로 확인")
    print("=" * 52)
    print(f"  {mark(bool(ad.get('ad_id')))} 광고 번호(ad_id) : {ad.get('ad_id') or '(비어있음)'}")
    print(f"  {mark(bool(ad.get('page_name')))} 페이지 이름      : {ad.get('page_name') or '(비어있음)'}")
    print(f"  {mark(bool(ad.get('caption')))} 캡션(본문)       : {(ad.get('caption') or '(비어있음)')[:40]}")
    print(f"  {mark(bool(ad.get('cta_text')))} 버튼 문구(CTA)   : {ad.get('cta_text') or '(비어있음)'}")
    print(f"  {mark(bool(ad.get('landing_url')))} 랜딩 주소        : {(ad.get('landing_url') or '(비어있음)')[:40]}")
    print(f"  {mark(bool(ad.get('media_urls')))} 소재(이미지/영상): {len(ad.get('media_urls') or [])}개")
    print(f"  {mark(ad.get('active_days') is not None)} 게재일수         : {ad.get('active_days')}")
    print(f"  {mark(bool(ad.get('platforms')))} 노출 플랫폼      : {ad.get('platforms') or '(비어있음)'}")
    print("=" * 52)

    done = all([
        ad.get("caption"), ad.get("media_urls"),
        ad.get("active_days") is not None,
    ])
    if done:
        print("  🎉 완성! 캡션·소재·게재일까지 전부 뽑혔어요.")
    else:
        print("  아직 비어있는 칸(❌)이 있어요. 워크샵 가이드 '보너스 단계'를")
        print("  클로드 코드에 붙여넣어서 scraper/extractor.py 를 채워보세요.")


if __name__ == "__main__":
    main()
