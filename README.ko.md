# photoEditer

[Read in English](README.md)

photoEditer, 또는 TonePilot Local은 Codex로 만든 RAW 우선 로컬 사진 보정 추천 도구야. AI 생성 사진이 아니라, 네가 직접 찍은 진짜 사진을 분석하는 데 초점을 둔다.

원래 의도한 흐름은 Lightroom에 가깝다. 가능하면 RAW 파일을 원본 기준으로 삼고, 원본 촬영 데이터를 분석해서 기술적인 부족한 점을 피드백한 뒤, 원하는 분위기 키워드에 맞춰 보정값과 미리보기를 제안하고 JPEG/PNG 결과물로 내보낸다.

핵심 흐름:

```text
RAW 사진 -> 이미지 분석 -> 스타일 목표 -> 히스토그램 기반 후보 -> 미리보기 -> JPEG/PNG export
```

## 무엇을 하나

- `rawpy`가 설치된 환경에서 RAW 파일 불러오기
- JPEG, PNG, TIFF는 보조 import/fallback 포맷으로 지원
- 가능한 메타데이터 추출
- luma, RGB, saturation 히스토그램 계산
- 하이라이트 클리핑, 암부 뭉개짐, 낮은 대비, 과채도, 컬러 캐스트 위험 감지
- 한국어/영어 스타일 프롬프트 해석
- Natural, Style, Bold 3개 보정 후보 생성
- 로컬에서 실제 preview 렌더링
- 보정 결과물을 JPEG/PNG로 export
- 선택한 보정값 JSON export

## 무엇은 아직 안 하나

- 클라우드 AI 사진 편집기가 아님
- 애니메이션풍 합성 이미지 생성 도구가 아님
- 아직 Lightroom을 완전히 대체하지는 않지만, RAW 원본에서 결과물로 가는 비슷한 흐름을 지향함
- 계정, 결제, 클라우드 API가 필요 없음

## 기술 스택

- Frontend: Vite, React, TypeScript, Tailwind CSS, Recharts
- Backend: Python, FastAPI, Pydantic, NumPy, Pillow
- Optional: RAW import용 rawpy, exifread, OpenCV
- Workspace: pnpm monorepo

## 로컬 설치

```powershell
corepack enable
pnpm install
```

Windows에서 Corepack 권한 문제가 있으면:

```powershell
npx pnpm@10.14.0 install
```

## 백엔드 실행

```powershell
cd apps/backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
python -m uvicorn app.main:app --reload --port 8765
```

RAW 지원까지 설치하려면:

```powershell
pip install -e ".[dev,raw]"
```

## 프론트엔드 실행

다른 터미널에서:

```powershell
pnpm --filter @tonepilot/desktop dev
```

루트에서 둘 다 실행하려면:

```powershell
pnpm dev
```

## 테스트

```powershell
cd apps/backend
pytest
```

## API 개요

- `GET /health`: 백엔드 상태 확인
- `POST /api/images/analyze`: 이미지 업로드 및 분석
- `POST /api/recommend`: 스타일 프롬프트 기반 보정 후보 생성
- `POST /api/preview`: 선택한 보정값으로 preview 렌더링
- `GET /api/previews/{filename}`: 생성된 preview 제공
- `POST /api/export/preset-json`: 선택한 보정값 JSON export
- `POST /api/export/rendered-image`: 보정 결과물을 JPEG/PNG로 export

자세한 내용은 [docs/API.md](docs/API.md)를 참고.

## 이미지 분석 방식

RAW 파일은 optional `rawpy`로 읽어서 RAW 센서 데이터와 렌더링 가능한 RGB 작업 이미지를 만든다. black level, white level, mean, p99, RAW histogram 같은 RAW 전용 통계를 잡고, 그 다음 JPEG/PNG/TIFF와 동일하게 RGB/luma/saturation 분석을 수행한다.

## 추천 방식

MVP는 룰 기반 스타일 해석을 사용한다. 예를 들어 `시원한 일본 여름 느낌`은 `cool_japanese_summer`로 매핑된다. 추천 엔진은 이 스타일 목표와 히스토그램 분석, 위험 플래그를 조합해서 Natural, Style, Bold 후보를 만든다.

## 현재 제한

- preview 렌더링은 근사치이며 Lightroom과 동일하지 않음
- RAW 지원은 optional `rawpy`에 의존하며 아직 초기 파이프라인
- CLIP, aesthetic scoring, segmentation, ONNX 모델 연동은 향후 모듈
- export는 현재 JPEG/PNG 결과물과 JSON 보정값을 지원하고 XMP/LUT는 아직 없음

## 로드맵

[docs/ROADMAP.md](docs/ROADMAP.md)를 참고.
