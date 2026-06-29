#!/bin/bash
# 더블클릭하면 설치 → 대시보드 켜기까지 자동으로 합니다.
cd "$(dirname "$0")" || exit 1

echo "🌸 경쟁사 광고 레퍼런스 수집기 — 준비 시작"
echo "-------------------------------------------"

# 1) 파이썬 확인
if ! command -v python3 >/dev/null 2>&1; then
  echo "❌ python3 가 없어요. https://www.python.org 에서 파이썬을 먼저 설치해 주세요."
  echo "   (설치 후 이 파일을 다시 더블클릭하세요.)"
  read -r -p "엔터를 누르면 닫혀요..." _
  exit 1
fi

# 2) 전용 짐가방(.venv) 만들기 — 처음 한 번만
if [ ! -d ".venv" ]; then
  echo "📦 처음이라 짐가방(.venv)을 만들고 필요한 것들을 설치할게요. 몇 분 걸려요..."
  python3 -m venv .venv
  ./.venv/bin/pip install --upgrade pip >/dev/null 2>&1
  ./.venv/bin/pip install -r requirements.txt
else
  echo "✅ 짐가방이 이미 있어요. 바로 켭니다."
fi

# 3) 대시보드 켜기
echo "-------------------------------------------"
echo "🚀 대시보드를 켭니다. 잠시 뒤 브라우저가 열려요."
echo "   (안 열리면 http://localhost:8501 로 접속)"
echo "   끄려면 이 창에서 Control+C 를 누르세요."
echo "-------------------------------------------"
./.venv/bin/streamlit run dashboard/app.py
