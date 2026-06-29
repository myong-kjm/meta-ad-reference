# 경쟁사 광고 레퍼런스 수집기 — 워크샵용 🌸

> 클로드 코드(AI 비서)와 **핑퐁하면서 같이 완성**하는 실습 프로젝트예요.
> 경쟁사(예: 클래스101)의 페이스북·인스타 광고를 모아 한 화면에서 훑어보는 도구입니다.

## 이게 뭔가요?

- 거의 다 만들어진 프로그램이에요. **딱 2곳만 비어 있고**, 그걸 클로드 코드랑 같이 채웁니다.
- 코드를 직접 칠 필요 없어요. 준비된 **프롬프트를 복사해서 붙여넣기**만 하면 됩니다.
- 연습용 광고 40개가 들어있어서, 다운받자마자 바로 화면이 떠요.

## 30초 시작 (더블클릭)

폴더 안에서 본인 컴퓨터에 맞는 파일을 **더블클릭**하세요. 끝.
- **맥(Mac)** → `START-Mac.command`
- **윈도우(Windows)** → `START-Windows.bat`

설치 → 대시보드 켜기까지 자동으로 해줍니다. 브라우저가 안 열리면 http://localhost:8501

> 맥에서 "확인되지 않은 개발자" 경고가 뜨면: `START-Mac.command` 우클릭 → **열기** → **열기**.
> 윈도우에서 파란 보호 화면이 뜨면: **추가 정보** → **실행**.

직접 입력하고 싶다면:
```bash
# 맥 / 리눅스
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
streamlit run dashboard/app.py
```
```bat
REM 윈도우 (명령 프롬프트)
py -m venv .venv & .venv\Scripts\activate
pip install -r requirements.txt
streamlit run dashboard\app.py
```

## 그다음엔?

➡️ **[워크샵-가이드.md](워크샵-가이드.md)** 를 여세요. 단계별로,
"클로드 코드에 이걸 그대로 붙여넣으세요" 프롬프트가 다 적혀 있어요.

| 단계 | 무엇을 | 어디를 |
|---|---|---|
| 1단계 (필수) | 사이드바 필터 살리기 | `dashboard/app.py` |
| 2단계 (보너스) | 광고 알맹이 뽑아내기 | `scraper/extractor.py` |

## 새 경쟁사 추가 (터미널)

대시보드에는 추가 버튼이 없어요. 경쟁사는 **터미널에서 URL을 직접 넣어** 등록합니다.
광고 라이브러리에서 그 페이지를 연 뒤 주소창 URL을 통째로 붙여넣으면 `view_all_page_id` 숫자를
자동으로 뽑아 **등록 + 즉시 수집**합니다. (config.json에도 자동 추가돼 매일 자동수집 목록에 들어감)

```bash
# URL 통째로
python scraper/main.py --url "https://www.facebook.com/ads/library/?...view_all_page_id=1947160905536967"
# 페이지 ID 숫자 + 이름
python scraper/main.py --url 1947160905536967 --name "클래스101"
# 창 없이 백그라운드(headless)로 수집
python scraper/main.py --url 1947160905536967 --headless
```

## 토큰(=비용) 아끼는 법

클로드 코드는 쓸수록 사용량이 듭니다. **한 번에 하나씩, 고칠 곳을 콕 집어, 짧게** 부탁하는 게 핵심.
자세한 5가지 습관은 [워크샵-가이드.md](워크샵-가이드.md) 위쪽에 있어요.
(이 폴더의 `CLAUDE.md` 덕분에 클로드가 구조를 다시 안 뒤져도 돼서, 이미 토큰이 많이 아껴집니다.)

## 폴더 구조 (참고만)

```
START-Mac.command / START-Windows.bat   더블클릭 시작 (맥 / 윈도우)
dashboard/      보는 화면 (대시보드)
scraper/        광고 모으는 코드
scripts/        보너스 테스트·자동 실행 스크립트
data/           연습용 샘플 광고가 들어있는 곳
워크샵-가이드.md   ★ 여기부터 보세요
CLAUDE.md       클로드 코드가 자동으로 읽는 안내문
docs/자동화-운영-매뉴얼.md   실전(진짜 수집·매일 자동화·노션) 안내
```

---
*실습/연구 목적. 공개된 광고만 다룹니다. 진짜 수집은 본인 컴퓨터에서, 하루 1회만.*
