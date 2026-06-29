#!/bin/bash
# launchd 설치 스크립트 — 매일 오전 8시 실행 등록.

set -e

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PLIST_SRC="$PROJECT_ROOT/scripts/com.halice.ad-scraper.plist"
PLIST_DST="$HOME/Library/LaunchAgents/com.halice.ad-scraper.plist"

mkdir -p "$HOME/Library/LaunchAgents"

# 템플릿의 __PROJECT_PATH__ 치환
sed "s|__PROJECT_PATH__|$PROJECT_ROOT|g" "$PLIST_SRC" > "$PLIST_DST"

# 기존 등록 있으면 제거
launchctl unload "$PLIST_DST" 2>/dev/null || true

# 등록
launchctl load "$PLIST_DST"

echo "✅ 매일 오전 8시 자동 실행 등록 완료"
echo ""
echo "확인: launchctl list | grep halice"
echo "수동 실행 테스트: launchctl start com.halice.ad-scraper"
echo "제거: launchctl unload $PLIST_DST"

# 스크립트에 실행 권한 부여
chmod +x "$PROJECT_ROOT/scripts/run_daily.sh"
