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

## 가장 쉬운 실행

Windows 10/11 PowerShell에서 아래 명령 하나로 설치:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -Command "$p=Join-Path $env:TEMP 'photo-install.ps1'; Invoke-WebRequest -UseBasicParsing 'https://raw.githubusercontent.com/r2gul4r/photoEditer/main/install.ps1' -OutFile $p; & $p"
```

이 원격 명령은 `install.ps1`이 GitHub `main` 브랜치에 올라간 뒤부터 동작한다.

이 명령은 다음을 자동으로 처리한다:

- Node.js LTS 설치 확인/설치
- Python 3.12 설치 확인/설치
- GitHub에서 photoEditer ZIP 다운로드
- 기본 위치 `~/TonePilot/photoEditer`에 압축 해제
- `photo` 전역 명령 등록
- 프로젝트 의존성 자동 설치

사용자가 직접 `photo install`을 입력할 필요는 없다. 설치가 끝나면 어느 폴더에서 PowerShell을 열어도:

```powershell
photo dev
```

`photo dev`는 로컬 주소를 출력하고 브라우저를 자동으로 연다. 자동으로 열리지 않으면 출력된 로컬 주소를 직접 열면 된다. 기본은 `http://127.0.0.1:5173/`이고, 이미 사용 중이면 `5173-5199` 범위에서 다른 포트를 골라 출력한다. Codex는 선택사항이며, 없으면 로컬 Rules 모드로 실행된다.

백엔드 venv와 Python 패키지는 매번 다시 설치하지 않는다. 첫 실행이나 환경이 깨진 경우에만 준비하고, 이후 `photo dev`, `pnpm dev`, `pnpm backend:dev`는 이미 준비된 venv를 자동으로 재사용한다.

이미 저장소를 직접 내려받은 개발자는 프로젝트 폴더에서 `npm.cmd link`, `photo install`, `photo dev` 순서로 실행해도 된다.

## photo 명령어

`photo`는 설치 후 어느 폴더에서든 실행할 수 있는 전역 명령이다.

| 명령 | 설명 |
| --- | --- |
| `photo install` | 의존성을 다시 설치하거나 복구한다. 원클릭 설치 때는 자동으로 실행된다. |
| `photo dev` | 로컬 웹 앱을 실행하고 브라우저를 연다. 준비가 빠져 있으면 한 번만 보정하고, 이후에는 기존 환경을 재사용한다. |
| `photo doctor` | Node/Python/백엔드 패키지/RAW 지원 설치 상태를 확인한다. |
| `photo setup` | 백엔드 Python 환경만 다시 준비한다. |
| `photo backend` | 백엔드 API 서버만 실행한다. |
| `photo desktop` | 프론트엔드 Vite 서버만 실행한다. |
| `photo test` | 백엔드 테스트와 프론트엔드 빌드를 같이 실행한다. |

## 수동 설치

```powershell
corepack enable
pnpm install
pnpm run setup
```

Windows에서 Corepack 권한 문제가 있으면:

```powershell
npx pnpm@10.14.0 install
npx pnpm@10.14.0 run setup
```

설치 상태만 확인하려면:

```powershell
pnpm run doctor
```

`rawpy` 설치가 실패하면 JPEG/PNG/TIFF 모드로 계속 실행된다. RAW 지원 설치를 다시 시도하려면:

```powershell
pnpm run setup -- --retry-raw
```

## 실행

루트에서 프론트/백엔드를 같이 실행:

```powershell
pnpm dev
```

`pnpm dev`도 백엔드 환경이 없을 때만 setup을 한 번 실행한다. 정상 설치 후에는 venv와 백엔드 의존성을 반복 설치하지 않는다.

백엔드만 실행:

```powershell
pnpm backend:dev
```

프론트엔드만 실행:

```powershell
pnpm desktop:dev
```

## Codex 연결

`pnpm dev`로 시작하면 백엔드가 Codex 명령을 자동 탐색한다.

- `TONEPILOT_CODEX_COMMAND` 환경변수가 있으면 그 값을 사용
- PATH에 있는 `codex` 사용
- Windows Codex 앱 설치 경로 `%LOCALAPPDATA%\OpenAI\Codex\bin\*\codex.exe` 자동 탐색

Codex가 없거나 로그인되어 있지 않으면 앱은 꺼지지 않고 로컬 Rules 추천으로 fallback한다. 연결 상태만 확인:

```powershell
pnpm backend:smoke:codex-status
```

실제 Codex 추천 턴까지 확인하려면 아래 명령을 쓸 수 있다. 이 명령은 실제 사용량/쿼터를 소비할 수 있다.

```powershell
pnpm backend:smoke:codex
```

추후 로컬 AI는 이 Codex 경로와 같은 provider 인터페이스 뒤에 붙이는 방향으로 유지한다. 즉 실행 흐름은 `pnpm dev` 그대로 두고, AI 제공자만 교체하는 구조를 목표로 한다.

## 테스트

```powershell
pnpm backend:test
pnpm desktop:build
```

Codex app-server smoke check:

```powershell
pnpm backend:smoke:codex-status
pnpm backend:smoke:codex
```

두 번째 명령은 실제 Codex 추천 턴을 시작하므로 Codex 사용량/쿼터를 소비할 수 있다.

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
