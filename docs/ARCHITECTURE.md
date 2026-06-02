# Architecture

## 구성

```text
apps/desktop   React/Vite UI
apps/backend   FastAPI local API
packages/shared TypeScript shared schemas
```

## 데이터 흐름

1. 사용자가 RAW 파일을 선택한다. JPEG/PNG/TIFF는 보조 import 포맷으로 허용한다.
2. 프론트엔드가 `POST /api/images/analyze`로 파일을 보낸다.
3. 백엔드가 원본을 로컬 저장소에 보관하고 분석 결과를 메모리에 연결한다.
4. 사용자가 스타일 프롬프트를 입력한다.
5. 프론트엔드가 `POST /api/recommend`를 호출한다.
6. 백엔드가 스타일 해석과 이미지 분석 결과를 조합해 후보 3개를 만든다.
7. 사용자가 후보를 선택하면 `POST /api/preview`가 실제 preview를 만든다.
8. 프론트엔드는 before/after 비교와 보정값을 표시한다.
9. 사용자가 결과물을 export하면 `POST /api/export/rendered-image`가 JPEG/PNG 파일을 생성한다.

## 확장 지점

- `services/raw_analysis.py`: RAW 분석
- `services/style_interpreter.py`: 룰 기반 스타일 매핑
- `services/recommendation_engine.py`: 후보 생성
- `services/renderer.py`: preview 렌더링
- 향후 CLIP, segmentation, ONNX 모델은 별도 서비스로 붙인다.
