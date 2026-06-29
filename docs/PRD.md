# 광고 레퍼런스 자동 수집기 (Pro) — PRD

> 마케터를 위한 페이스북 광고 라이브러리 자동 스크래퍼 + Streamlit 대시보드
> 작성일: 2026-05-25
> 대상: 콘마(할리스.ai) 1주차 강의 응용 / 마케팅 실무자

---

## 1. 한 줄 요약

**경쟁사 페이스북 광고 라이브러리를 매일 오전 9시에 자동으로 긁어서, 어제 새로 올라온 광고와 지난 7일간 활성 중인 광고를 본인 컴퓨터의 Streamlit 대시보드에서 시각적으로 본다.**

---

## 2. 왜 만드는가 (Why)

### 마케터의 현실 문제
- 경쟁사 위너 광고는 광고 라이브러리에 다 공개돼있지만 **매일 손으로 확인하기 귀찮다.**
- 어제 새로 올라온 광고만 봐도 시장 흐름이 보이는데, 매일 들어가서 정렬·필터 거는 게 일.
- Foreplay 같은 유료 도구는 월 $30~50이고, 한국 광고는 데이터 빈약.
- Apify 같은 매니지드 스크래퍼는 가격이 1,000개당 $5~6 — 매일 돌리면 누적 부담.

### 이 도구의 가치
- **본인 컴퓨터 + 본인 IP로 도는 무료 도구** → 외부 비용 0원.
- **봇 차단 위험 최소화** (본인 Chrome 프로필 재사용, 사람형 행동 시뮬레이션).
- 데이터를 SQLite로 본인 컴퓨터에 영구 보관 → 시간 누적되면 위너 패턴 발견 가능.
- Streamlit 대시보드 = 마케터가 엑셀처럼 쓰는 시각 도구.

---

## 3. 사용자 시나리오 (User Story)

### 시나리오 A — 매일 아침 루틴
1. 마케터 출근 9시 5분, 노트북 열림
2. (백그라운드에서) 9시에 launchd가 스크래퍼 실행 → 5분 이내 완료
3. 마케터가 `streamlit run dashboard/app.py` 실행
4. **"어제 신규 광고" 탭 열기** → 등록된 경쟁사 10곳에서 어제 새로 올라온 광고 N개를 카드 그리드로 봄
5. 영상은 미리보기 재생, 이미지는 썸네일, 카피는 전문 확인
6. 마음에 드는 광고에 "메모" + "위너 후보" 태그 → SQLite에 저장
7. **"지난 7일 활성" 탭 열기** → 7일 넘게 살아남은 광고 = 거의 확정 위너. 패턴 분석.

### 시나리오 B — 새 경쟁사 추가
1. 마케터가 인스타에서 새 경쟁사 발견
2. `dashboard/app.py`의 "페이지 관리" 탭에서 페이지 URL 또는 `view_all_page_id` 입력
3. 저장 → 다음 9시 실행부터 자동 수집됨

---

## 4. 기능 요구사항 (Functional Requirements)

### 4.1 스크래핑 (`scraper/`)

| 요구 | 내용 |
|---|---|
| 입력 | 경쟁사 페이지 ID 목록 (SQLite `competitors` 테이블) |
| 모드 1 | `sort_data[mode]=relevancy_monthly_grouped` → 최신순(어제 신규) |
| 모드 2 | `sort_data[mode]=total_impressions` → 노출수 많은 순(위너 추정) |
| 필터 | `active_status=active&country=KR&ad_type=all&media_type=all` 고정 |
| 출력 | 각 광고의 ad_id, 페이지명, 캡션 전문, 미디어(영상/이미지) 로컬 다운로드, 랜딩 URL, 활성 시작일, 활성 기간(일), 광고 플랫폼(FB/IG/Messenger/Threads), 첫 발견일, 마지막 확인일 |
| 미디어 저장 | `data/media/<page_id>/<ad_id>/{video.mp4, image_0.jpg, image_1.jpg, ...}` |
| 점진 수집 | 기존 SQLite에 있는 ad_id는 `last_seen_at`만 업데이트, 신규는 `first_seen_at`도 기록 |

### 4.2 봇 회피 (Anti-Detection)

| 전략 | 구현 |
|---|---|
| **본인 Chrome 프로필 재사용** | `~/Library/Application Support/Google/Chrome/Default` 가져다 사용 → 메타가 보기에 사람의 로그인된 브라우저 |
| **헤드리스 비활성화** | `headless=False` — 실제 창 띄움. 봇 시그널 줄임 |
| **playwright-stealth** | webdriver 플래그, navigator.plugins 등 봇 지문 제거 |
| **랜덤 딜레이** | 페이지 진입 후 3~7초, 스크롤 사이 1~3초, 액션 사이 0.5~1.5초 |
| **사람형 스크롤** | 부드러운 스크롤 (한 번에 끝까지 X), 가끔 위로 스크롤 |
| **마우스 무브** | 페이지 진입 시 랜덤 좌표로 마우스 이동 |
| **하루 1회 제한** | 매일 9시 1회만 실행. 시간 분산 안 함 |
| **경쟁사 간 휴식** | 페이지 5개 처리할 때마다 30~60초 휴식 |
| **에러 시 재시도 안 함** | 차단되면 즉시 중단, 다음날 재시도 (재시도 자체가 봇 시그널) |

### 4.3 데이터 모델 (SQLite — `data/ads.db`)

```sql
-- 경쟁사 관리
CREATE TABLE competitors (
  page_id TEXT PRIMARY KEY,
  page_name TEXT,
  notes TEXT,
  added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  is_active BOOLEAN DEFAULT 1
);

-- 광고 본체
CREATE TABLE ads (
  ad_id TEXT PRIMARY KEY,
  page_id TEXT,
  page_name TEXT,
  caption TEXT,
  cta_text TEXT,
  landing_url TEXT,
  display_url TEXT,           -- "CLASS101.NET" 같은 표시 도메인
  platforms TEXT,             -- JSON: ["facebook", "instagram"]
  start_date DATE,            -- 활성 시작일
  active_days INTEGER,        -- 활성 기간 (스크래핑 시점 기준)
  is_active BOOLEAN,
  has_video BOOLEAN,
  media_paths TEXT,           -- JSON: ["media/<page>/<ad>/video.mp4", ...]
  first_seen_at TIMESTAMP,    -- 우리 DB에 처음 들어온 시점
  last_seen_at TIMESTAMP,     -- 마지막으로 활성 확인한 시점
  raw_json TEXT               -- 원본 GraphQL 응답 (디버그용)
);

-- 마케터 메모/태그
CREATE TABLE annotations (
  ad_id TEXT PRIMARY KEY,
  is_winner_candidate BOOLEAN DEFAULT 0,
  tags TEXT,                  -- JSON: ["LMF형", "감정묘사", ...]
  memo TEXT,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 4.4 Streamlit 대시보드 (`dashboard/app.py`)

5개 탭:

1. **📅 어제 신규** — `first_seen_at`이 어제인 광고. 카드 그리드, 페이지별 그룹.
2. **🔥 지난 7일 활성** — 7일 이상 살아남은 활성 광고. 활성 기간 내림차순.
3. **🏢 페이지별 비교** — 경쟁사 선택 → 그 페이지의 전체 광고 타임라인.
4. **⭐ 위너 후보** — `is_winner_candidate=1`로 마킹한 광고들.
5. **⚙️ 페이지 관리** — 경쟁사 추가/삭제, 마지막 수집 시각 확인, 수동 재실행 버튼.

각 광고 카드 구성:
- 상단: 페이지명 + 활성 기간 배지 ("12일째 활성")
- 미디어: 영상이면 `st.video`, 이미지면 `st.image` (다중 이미지 = 캐러셀)
- 캡션: 전문 (긴 건 expander)
- CTA + 랜딩 URL: 클릭 가능 링크
- 하단: "⭐ 위너 후보" 토글 + 메모 입력칸 + 태그 멀티셀렉트

### 4.5 매일 9시 실행 (`scripts/run_daily.sh` + launchd plist)

- macOS launchd로 `com.halice.ad-scraper.plist` 등록
- 매일 09:00에 `scraper/main.py` 실행
- 로그는 `data/logs/YYYY-MM-DD.log`
- 노트북 닫혀있으면 다음 깨어났을 때 실행 (launchd 기본 동작)

---

## 5. 비기능 요구사항

| 항목 | 기준 |
|---|---|
| 1회 실행 시간 | 경쟁사 10곳 × 평균 30개 광고 기준 5~10분 이내 |
| 디스크 사용량 | 1,000개 광고 누적 시 ~5GB (영상 위주) |
| 봇 차단 시 행동 | 즉시 종료, 로그 기록, 다음 실행은 다음날 |
| 차단 복구 | 본인 Chrome 프로필 재로그인 + 24시간 대기 후 재시도 |
| 강의용 설치 시간 | 학생 1명 기준 30분 이내 (Python + Playwright + 의존성) |

---

## 6. 기술 스택

| 영역 | 기술 | 이유 |
|---|---|---|
| 스크래퍼 | Python + Playwright + playwright-stealth | GraphQL 가로채기 + stealth 플러그인 |
| DB | SQLite | 본인 컴퓨터에 파일 하나로 끝, 백업 쉬움 |
| 대시보드 | Streamlit | 마케터 친화, `streamlit run` 한 줄 |
| 스케줄러 | macOS launchd | cron보다 노트북 sleep 친화 |
| 패키지 관리 | `uv` 또는 `pip` + `requirements.txt` | 마케터는 uv가 더 빠르고 단순 |

---

## 7. 명시적으로 안 만드는 것 (Out of Scope)

- 클라우드 배포 (Vercel/AWS/GCP) — 봇 차단 위험. 무조건 로컬.
- 다중 사용자 / 팀 공유 — 본인 컴퓨터 1인용. 팀 공유는 시트 export로 우회.
- 정치/사회 이슈 광고 — 메타 API 쓰면 안정적이지만 본 도구 범위 밖.
- 자동 카피 생성 / 분석 — 2주차 카피 스킬에서 별도 처리.
- 실시간 알림 (슬랙 등) — 응용 단계, 보너스 챕터에서 다룸.

---

## 8. 리스크 & 완화책

| 리스크 | 영향 | 완화 |
|---|---|---|
| 메타가 광고 라이브러리 HTML/GraphQL 변경 | 스크래퍼 깨짐 | 로그에 명확한 에러 메시지, 셀렉터 한 곳에 모아두기, 학생용 "복구 가이드" 문서 |
| 봇 탐지로 IP 차단 | 며칠~몇 주 못 씀 | 본인 Chrome 프로필 + 하루 1회 + 사람형 행동으로 확률 최소화. 차단 시 24시간 대기 |
| 메타 ToS 위반 우려 | 법적 리스크 | 공개 정보만 수집, 로그인 강제 안 함, 개인 학습/연구 목적 명시 |
| 디스크 가득 참 | 영상 누적 | "60일 이상 비활성 광고는 미디어만 삭제(메타데이터 유지)" 정리 스크립트 |

---

## 9. 마일스톤

1. **PRD + 폴더 구조** (지금)
2. **스크래퍼 코어** — URL 1개 받아 광고 N개 수집까지
3. **DB 적재** — SQLite 스키마 + INSERT/UPDATE 로직
4. **Streamlit 최소 버전** — 어제 신규 탭 1개만 작동
5. **launchd 스케줄링**
6. **나머지 탭 + 메모/태그**
7. **강의 스크립트 + README**

---

## 10. 강의용 메모

이 도구를 1주차 강의에 어떻게 녹일지:

- **본 강의(1주차)**: 기존 URL 붙여넣기 + Vercel 배포 버전 그대로. 5단계 흐름 학습.
- **1주차 보너스 또는 4~5주차 응용**: 본 도구를 "자동화 확장 버전"으로 소개.
  - 핵심 메시지: "수동 수집 익혔으면, 같은 흐름을 자동으로"
  - 학생들한테 무조건 강요 X. 자동화에 흥미 있는 학생만 따라옴.
  - 봇 차단 위험을 솔직히 알림 — "강의 자료니까 깨질 수 있다, 그땐 클로드한테 셀렉터 다시 짜달라고"
