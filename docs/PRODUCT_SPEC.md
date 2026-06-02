# TonePilot Local Product Spec

## 목표

로컬 데스크톱 앱에서 사진을 분석하고, 사용자가 입력한 한국어/영어 스타일 키워드를 룰 기반 스타일 타깃으로 해석한 뒤, 히스토그램과 위험 플래그를 고려한 보정 후보를 추천한다.

핵심 원칙:

```text
Keyword -> style target -> histogram-aware candidates -> actual preview -> objective safety checks
```

## MVP 범위

- 로컬 백엔드 서버
- Vite React 데스크톱 UI
- JPEG, PNG, TIFF 업로드
- RAW 분석 스캐폴드
- EXIF 메타데이터 best-effort 추출
- luma/RGB/saturation 히스토그램 분석
- 위험 플래그 계산
- 룰 기반 스타일 해석
- Natural, Style, Bold 후보 생성
- 실제 미리보기 렌더링
- 보정값 JSON export

## 제외 범위

- diffusion 기반 애니메이션 변환
- 클라우드 API
- Lightroom 연동
- 로그인, 결제, 계정
- 모바일 앱
- ML 학습 파이프라인

## 필수 스타일

- 시원한 일본 여름 느낌
- 애니메이션 느낌
- 청량한 필름톤
- 따뜻한 카페톤
- 시네마틱 무드
- 깨끗한 인스타그램톤

## 완료 기준

- 백엔드가 FastAPI로 시작된다.
- 프론트엔드가 Vite React로 시작된다.
- 이미지 업로드 후 분석 결과가 UI에 표시된다.
- 스타일 키워드 입력 후 후보 3개가 생성된다.
- 선택 후보를 실제 preview로 렌더링한다.
- 선택 보정값을 JSON으로 export할 수 있다.
- 핵심 백엔드 로직 테스트가 있다.

