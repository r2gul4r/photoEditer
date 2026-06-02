# TonePilot Local

TonePilot Local은 사진을 업로드하면 로컬 백엔드가 히스토그램, 메타데이터, 채도, 클리핑 위험을 분석하고, 사용자가 입력한 스타일 키워드에 맞춰 보정 후보 3개를 추천하는 데스크톱 지향 MVP다.

이 버전은 생성형 이미지 변환 도구가 아니다. 클라우드 API를 쓰지 않고, `키워드 -> 스타일 타깃 -> 히스토그램 기반 후보 -> 실제 미리보기 -> 안전성 점검` 흐름을 구현한다.

## 기술 스택

- Frontend/Desktop: Vite, React, TypeScript, Tailwind CSS, Recharts
- Backend: Python 3.11+, FastAPI, Pydantic, NumPy, Pillow
- Optional: rawpy, exifread, OpenCV
- Storage: MVP는 로컬 파일과 프로세스 메모리 저장소

## 로컬 실행

```powershell
cd tonepilot-local
corepack enable
pnpm install

cd apps/backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8765
```

다른 터미널에서:

```powershell
cd tonepilot-local
pnpm --filter @tonepilot/desktop dev
```

루트에서 동시에 실행하려면:

```powershell
pnpm dev
```

Corepack이 권한 문제로 실패하는 Windows 환경에서는 전역 pnpm 설치 없이 아래처럼 실행할 수 있다.

```powershell
cd tonepilot-local
npx pnpm@10.14.0 install
npx pnpm@10.14.0 dev
```

샘플 환경 변수는 [apps/backend/.env.example](apps/backend/.env.example), [apps/desktop/.env.example](apps/desktop/.env.example)에 있다.

## 테스트

```powershell
cd tonepilot-local/apps/backend
pytest
```

## API 개요

- `GET /health`: 백엔드 상태 확인
- `POST /api/images/analyze`: 이미지 업로드, 메타데이터와 히스토그램 분석
- `POST /api/recommend`: 스타일 키워드 기반 후보 3개 생성
- `POST /api/preview`: 후보 보정값을 실제 미리보기 이미지로 렌더링
- `GET /api/previews/{filename}`: 생성된 미리보기 파일 제공
- `POST /api/export/preset-json`: 선택한 보정값을 JSON으로 반환

자세한 내용은 [docs/API.md](docs/API.md)를 참고.

## 이미지 분석 방식

백엔드는 이미지를 RGB float `[0, 1]`로 변환한 뒤 luma, RGB 채널, HSV saturation 통계를 계산한다. `p01`, `p50`, `p99`, 256-bin 히스토그램과 함께 하이라이트 클리핑, 암부 뭉개짐, 과채도, 컬러 캐스트 위험을 휴리스틱으로 표시한다.

## 추천 방식

스타일 키워드는 룰 기반 매칭으로 해석한다. 예를 들어 `시원한 일본 여름 느낌`은 `cool_japanese_summer`로 해석되고, 스타일별 슬라이더 범위와 이미지 위험 플래그를 조합해 `Natural`, `Style`, `Bold` 후보를 만든다.

## 현재 제한

- Lightroom과 동일한 렌더링 엔진이 아니다.
- RAW는 `rawpy`가 설치되어 있을 때만 제한적으로 분석한다.
- 세그멘테이션, CLIP, 로컬 aesthetic scoring은 인터페이스/TODO만 남겼다.
- 프리셋 export는 JSON이며 XMP/LUT export는 후속 과제다.

## 로드맵

로드맵은 [docs/ROADMAP.md](docs/ROADMAP.md)에 정리되어 있다.
