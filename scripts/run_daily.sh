#!/bin/bash
# 매일 오전 8시 실행되는 광고 수집 스크립트.
# launchd가 이 스크립트를 호출. 결과는 data/logs/에 쌓임.

set -e

# 이 스크립트가 있는 폴더의 상위 = 프로젝트 루트
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT"

# 로그 파일 (오늘 날짜)
TODAY=$(date +%Y-%m-%d)
LOG_DIR="$PROJECT_ROOT/data/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/${TODAY}_cron.log"

echo "================================" >> "$LOG_FILE"
echo "시작: $(date)" >> "$LOG_FILE"
echo "================================" >> "$LOG_FILE"

# 가상환경이 있으면 활성화
if [ -d "$PROJECT_ROOT/.venv" ]; then
    source "$PROJECT_ROOT/.venv/bin/activate"
fi

# 단일 모드(신규/관련도순)만 실행 — 같은 페이지를 하루 2번 연속 로드(--mode both)하면
# 페북이 빈 결과(throttle)를 주기 쉬워서, footprint를 줄이려고 한 모드만 돌린다.
# 노출수순(winner)이 필요하면 대시보드 '지금 수집'을 따로 쓰거나 아래를 --mode both로.
python scraper/main.py --mode relevancy_monthly_grouped >> "$LOG_FILE" 2>&1

echo "================================" >> "$LOG_FILE"
echo "끝: $(date)" >> "$LOG_FILE"
echo "================================" >> "$LOG_FILE"
