# AI Correction Redesign Notes

작성일: 2026-06-03

## 현재 상태

TonePilot Local은 현재 다음 흐름으로 동작한다.

1. 사용자가 사진을 업로드한다.
2. 백엔드가 EXIF/RAW 메타데이터, RGB/luma/saturation histogram, risk flag를 분석한다.
3. 사용자가 입력한 `style_prompt`를 백엔드가 키워드 기반 스타일 정의로 해석한다.
4. `ai_mode=auto` 또는 `codex`이면 Codex app-server가 보정 후보를 만든다.
5. Codex가 실패하거나 `rules` 모드이면 rule-based recommender가 후보를 만든다.
6. 프론트는 후보 하나를 선택하고, 보정 슬라이더를 수동으로 수정한 뒤 preview/export한다.

현재 구현 위치:

- 프론트 추천 호출: `apps/desktop/src/App.tsx`, `apps/desktop/src/api/client.ts`
- 추천 라우터: `apps/backend/app/routers/recommend.py`
- Codex provider: `apps/backend/app/services/codex_app_server.py`
- Rules provider: `apps/backend/app/services/recommendation_engine.py`
- 스타일 해석: `apps/backend/app/services/style_interpreter.py`
- 레퍼런스 manifest 로딩: `apps/backend/app/services/reference_library.py`

## 현재 AI 보정 원리

프론트는 `/api/recommend`에 아래 값을 보낸다.

- `image_id`
- `style_prompt`
- `strength`
- `ai_mode`

백엔드는 먼저 `style_prompt`를 `STYLE_DEFINITIONS` 중 하나로 매핑한다. 이 단계에서 자유 입력은 `soft_film`, `cool_japanese_summer`, `anime_background`, `warm_cafe`, `cinematic_mood`, `clean_instagram` 같은 제한된 스타일 타깃으로 압축된다.

Codex 경로에서는 compact schema를 강제한다.

- 후보는 `natural`, `style`, `bold` 3개로 고정
- 각 후보는 37개 숫자 벡터
- 벡터 순서는 기본 슬라이더 + 8색 HSL
- 출력은 JSON만 허용
- 이미지가 RAW이면 Codex에는 원본 이미지가 첨부되지 않고 분석값만 들어간다

Rules 경로는 스타일별 `slider_prior`와 histogram risk flag를 조합한다. 예를 들어 highlight clipping이면 exposure/highlights/whites를 제한하고, too dark이면 exposure/shadows/blacks를 올린다.

## 왜 답답하게 느껴지는가

현재 구조는 "AI가 사진의 룩을 자유롭게 설계"하는 구조가 아니다. 더 정확히는 "고정 후보 슬롯 안에 보정 숫자를 채우는 구조"다.

문제점:

1. 후보 이름과 목적이 `Natural / Style / Bold`로 고정돼 있다.
2. 프롬프트가 먼저 제한된 스타일 정의로 압축된다.
3. Codex 출력이 37개 숫자 벡터라 설명력과 변주가 작다.
4. 레퍼런스 manifest는 UI에 보이지만 추천 prompt에는 아직 연결되지 않았다.
5. 사용자의 후속 피드백을 반영하는 delta 보정 API가 없다.
6. 강도는 1개 축뿐이라 사용자가 원하는 방향을 세밀하게 지정하기 어렵다.
7. 후보 선택 후 수동 조정은 가능하지만, AI와 사용자가 반복적으로 협업하는 구조는 아니다.

## Lightroom에서 배울 점

Lightroom의 핵심은 단일 자동 보정이 아니라 여러 조절 축을 유지하는 것이다.

공식 문서 기준으로 확인한 관련 개념:

- Histogram은 tonal range, shadow/highlight clipping, RGB readout을 보는 분석 표면이다.
- Color Mixer와 Point Color는 특정 색 범위의 hue/saturation/luminance를 조절한다.
- Tone Curve는 tonal range와 contrast를 더 직접적으로 조정한다.
- Masking/AI edits는 global edit과 local edit을 분리한다.
- Profile은 슬라이더 값을 덮어쓰지 않는 시작점/기반 룩으로 쓰인다.

참고:

- Adobe Lightroom Classic tone/color/histogram: https://helpx.adobe.com/uk/lightroom-classic/help/image-tone-color.html
- Adobe Color Mixer / Point Color: https://helpx.adobe.com/lightroom-classic/help/color-mixer.html
- Adobe AI Edit Status: https://helpx.adobe.com/uk/lightroom/web/edit-photos/manage-ai-edits.html

주의: Lightroom의 내부 구현, 에셋, 픽셀 UI를 복제하지 않는다. 공개 문서와 사용자가 소유한 이미지의 black-box 비교만 사용한다.

## 권장 방향

### 1. 후보 구조를 자유 후보로 바꾸기

현재:

- `natural`
- `style`
- `bold`

권장:

- AI가 후보 이름과 의도를 직접 만든다.
- 후보 수는 3개 이상 가능하게 한다.
- 후보는 서로 다른 편집 철학을 가져야 한다.

예:

- Clean Base
- Warm Film
- Cool Air
- Reference Match
- High Contrast B&W
- Skin Safe Portrait
- Experimental Color

API 변경 방향:

```json
{
  "candidates": [
    {
      "id": "clean_base",
      "name": "Clean Base",
      "intent": "기본 노출과 색 균형을 안정화",
      "recipe": {
        "profile": "neutral",
        "tone": {},
        "color": {},
        "hsl": {},
        "curve": {},
        "masks": []
      },
      "adjustments": {},
      "warnings": []
    }
  ]
}
```

### 2. 숫자 후보가 아니라 recipe 후보로 보여주기

사용자가 이해할 수 있게 후보를 아래 단위로 나눈다.

- Tone: exposure, contrast, highlights, shadows, whites, blacks
- Color: temperature, tint, vibrance, saturation
- Presence: clarity, texture, dehaze
- HSL / Point Color
- Curve
- Masks
- Risk protection

프론트는 각 섹션을 접고 펼 수 있게 만든다. 사용자는 AI 후보 전체를 적용하거나, 섹션 단위로 켜고 끌 수 있어야 한다.

### 3. 레퍼런스를 추천 입력에 연결하기

현재 `reference/` manifest는 로딩만 되고 추천 prompt에는 안 들어간다.

다음 단계:

1. `RecommendRequest`에 `reference_id` 또는 `reference_target_id` 추가
2. 백엔드에서 reference manifest/preset을 로딩
3. Codex prompt에 reference 목표와 preset 값을 포함
4. 후보 중 하나를 `Reference Match`로 생성
5. 추후에는 이미지 embedding/retrieval로 비슷한 레퍼런스를 자동 추천

### 4. 후속 수정형 AI 추가

새 endpoint 예:

```http
POST /api/recommend/refine
```

입력:

- 기존 candidate
- 사용자 instruction
- 보호 조건
- 현재 preview 상태

예시 instruction:

- "피부톤은 유지하고 배경만 더 차갑게"
- "하이라이트 날아가지 않게 더 밝게"
- "필름 느낌은 유지하되 채도 낮춰"
- "녹색을 덜 형광처럼"

이 endpoint는 전체 후보를 다시 만드는 것이 아니라 현재 후보의 delta만 반환한다.

### 5. 사용자 제어 축 추가

강도 하나로는 부족하다.

권장 control:

- Intensity: 전체 적용 강도
- Tone Contrast: 부드러움 vs 강한 대비
- Color Bias: warm vs cool
- Saturation Taste: muted vs vivid
- Highlight Protection
- Shadow Protection
- Skin Protection
- Experimentalness

이 값들은 AI prompt에도 들어가고, rule fallback에서도 multiplier로 써야 한다.

### 6. AI 상태와 신뢰도 표시

현재 `ai_status`는 `used/fallback/not_requested` 정도만 보여준다.

권장:

- AI 사용 여부
- fallback 여부
- 후보가 이미지 입력을 봤는지, 분석값만 봤는지
- reference 사용 여부
- clipping/saturation risk 이유
- 어떤 사용자 constraint를 지켰는지

사용자는 "이 후보가 왜 이렇게 나왔는지"를 알아야 수동 조정으로 이어갈 수 있다.

## 구현 순서

### Phase 1: 설명력 개선

- 후보 카드에 `intent`, `tone_summary`, `color_summary`, `risk_summary` 표시
- Codex compact output에 message를 후보별로 확장
- Rules 후보도 동일한 summary 생성

진행 상태:

- 2026-06-03: `CorrectionCandidate`에 optional explanation fields를 추가했다.
- 2026-06-03: Rules 후보와 Codex compact 후보가 `intent`, `tone_summary`, `color_summary`, `risk_summary`를 채우도록 했다.
- 2026-06-03: 프론트 후보 카드가 explanation fields를 표시하도록 했다.

### Phase 2: 자유 후보

- backend schema에서 candidate id literal 제한 완화
- Codex schema를 `natural/style/bold` 고정에서 후보 배열로 변경
- 프론트 후보 리스트가 동적 id/name을 받도록 변경

### Phase 3: 레퍼런스 연결

- `RecommendRequest.reference_id` 추가
- reference manifest/preset을 prompt payload에 포함
- `Reference Match` 후보 생성

### Phase 4: refine loop

- `/api/recommend/refine` 추가
- 기존 candidate + instruction -> delta adjustments 반환
- 프론트에 "추가 요청" 입력창 추가

### Phase 5: Lightroom-like advanced controls

- Tone Curve UI
- Color Mixer / Point Color UI
- Mask placeholder에서 실제 mask model/provider 연결
- recipe section apply/toggle

## ChatGPT 피드백 상태

현재 Codex 세션에는 ChatGPT 전용 connector/plugin이 없고, 설치 후보 목록에도 ChatGPT connector가 없다. 따라서 `@ChatGPT`에 별도 피드백 요청을 보내는 단계는 수행할 수 없었다.

대체로 수행한 것:

- 현재 worktree 분석
- Chrome 플러그인으로 로컬 앱 로드 검증
- Adobe 공식 Lightroom 문서 확인
- 현재 AI 보정 구조와 UX 한계 분석
- 다음 구현 방향 정리

ChatGPT connector가 사용 가능해지면 이 문서를 입력으로 보내 다음 질문을 요청하면 된다.

추천 질문:

1. 이 AI 보정 UX에서 사용자가 답답함을 느끼는 가장 큰 원인은 무엇인가?
2. Lightroom-like local editor에서 AI 후보를 어떻게 구조화해야 자유도와 안정성을 동시에 줄 수 있는가?
3. 레퍼런스 이미지 기반 보정을 MVP에서 어디까지 구현하는 것이 적절한가?
4. 후보 생성, refine loop, recipe editing 중 어떤 순서가 제품 완성도에 가장 큰 영향을 주는가?
