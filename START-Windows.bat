@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo.
echo  경쟁사 광고 레퍼런스 수집기 - 준비 시작
echo  -------------------------------------------

REM 1) 파이썬 찾기 (py 또는 python)
set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY (
  where python >nul 2>nul && set "PY=python"
)
if not defined PY (
  echo  [X] 파이썬이 없어요. https://www.python.org 에서 먼저 설치해 주세요.
  echo      설치 화면에서 "Add Python to PATH" 를 꼭 체크하세요.
  echo.
  pause
  exit /b 1
)

REM 2) 전용 짐가방(.venv) 만들기 - 처음 한 번만
if not exist ".venv\Scripts\streamlit.exe" (
  echo  [*] 처음이라 짐가방(.venv)을 만들고 필요한 것들을 설치할게요. 몇 분 걸려요...
  %PY% -m venv .venv
  ".venv\Scripts\python.exe" -m pip install --upgrade pip
  ".venv\Scripts\pip.exe" install -r requirements.txt
) else (
  echo  [OK] 짐가방이 이미 있어요. 바로 켭니다.
)

REM 3) 대시보드 켜기
echo  -------------------------------------------
echo  대시보드를 켭니다. 잠시 뒤 브라우저가 열려요.
echo  (안 열리면 http://localhost:8501 로 접속)
echo  끄려면 이 창에서 Ctrl+C 를 누르세요.
echo  -------------------------------------------
".venv\Scripts\streamlit.exe" run dashboard\app.py
pause
