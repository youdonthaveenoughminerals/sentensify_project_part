# 📘 Sentencify Phase 1 – 추천 API 내부 스펙 (Recommend ↔ Model)

작성일: 2025-11-17  
범위: **Phase 1 Step 1 – `/recommend` API와 내부 모델/룰/벡터 모듈 간 인터페이스 정의**

---

## 1. 목적

- FastAPI `/recommend` 엔드포인트와, 내부의
  - Rule 기반 스코어러 (**P_rule**),
  - Vector 기반 스코어러 (**P_vec**)
  사이의 **요청/응답 스키마를 고정**하기 위함이다.
- 모델팀이 P_rule/P_vec 구현을 교체하더라도,
  - `/recommend` 외부 Contract(FE ↔ BE, A/B/C/E 스키마)는 그대로 유지된다.

본 문서에서는 **함수형 인터페이스** 수준으로 정의하며,
Phase 1에서는 Stub/Mock을 사용해도 무방하다.

---

## 2. 전체 흐름 요약

1. FE → `/recommend` 호출 (phase1-front-spec.md 3.1 참조).
2. `/recommend` 내부에서:
   1. `context_full` 조립 (`context_prev + "\n" + selected + "\n" + context_next`).
   2. `context_hash = sha256(doc_id + ":" + context_full)` 계산.
   3. **Rule 모듈**에 요청 → `P_rule` 획득.
   4. **Vector 모듈**에 요청 → `P_vec` 획득.
   5. `P_final`로 최종 category 및 reco_options 선정.
   6. A/I/E 이벤트 생성 후 Kafka + 로그 저장.
3. `/recommend` Response로 insert_id, recommend_session_id, reco_options, P_rule, P_vec, context_hash 반환.

본 문서의 대상은 2-3, 2-4에 해당하는 **내부 호출 규칙**이다.

---

## 3. 공통 입력 컨텍스트 구조

두 모듈(P_rule, P_vec)은 동일한 기본 컨텍스트를 입력으로 받는다.

```ts
type RecommendContext = {
  doc_id: string;
  user_id: string | null;

  // 원문/문맥
  selected_text: string;
  context_prev: string | null;
  context_next: string | null;
  context_full: string;     // 서버에서 조립: prev + "\n" + selected + "\n" + next
  context_hash: string;     // sha256(doc_id + ":" + context_full)

  // 옵션 (FE에서 온 값)
  field: string | null;     // email/thesis/article/...
  language: string | null;  // ko/en/...
  intensity: string | null; // weak/moderate/strong
  user_prompt: string | null;

  // 메타
  request_ts: string;       // ISO8601, 서버에서 세팅
  api_version: string;
  schema_version: string;
};
```

Phase 1 Step 1에서는 `/recommend` 내부 함수 호출로만 사용하며,
향후 마이크로서비스로 분리할 경우 이 스키마를 그대로 HTTP/gRPC Payload로 사용할 수 있다.

---

## 4. Rule 모듈 인터페이스 (P_rule)

### 4.1 함수 시그니처 (논리)

```ts
// Python pseudo type
def compute_p_rule(ctx: RecommendContext) -> dict[str, float]:
    ...
```

- 입력: `RecommendContext`
- 출력: `P_rule` – 카테고리별 확률/점수 딕셔너리 (정규화 여부는 모듈 내부 정책)

### 4.2 출력 스키마

```jsonc
{
  "thesis": 0.5,
  "email": 0.3,
  "article": 0.2
}
```

- key: 카테고리 문자열 (phase1-meta.md, phase1-front-spec.md의 `field` domain과 일치)
- value: 0~1 범위의 score (합이 1이 아니어도 무방하나, Phase 1에서는 합 1을 권장)

### 4.3 Phase 1 Step 1 구현 규칙 (Stub)

- 현재는 모델팀 작업 전이므로, `compute_p_rule`은 **하드코딩 Stub**으로 두어도 된다.
  - 예: 선택된 텍스트/field에 키워드가 포함되면 그 카테고리에 가중치를 주는 정도.
- 중요한 것은:
  - 리턴 타입이 `dict[str, float]`로 고정된다는 점,
  - 카테고리 이름이 FE 옵션/로그 스키마에서 사용하는 값과 일치한다는 점이다.

---

## 5. Vector 모듈 인터페이스 (P_vec)

### 5.1 함수 시그니처 (논리)

```ts
def compute_p_vec(ctx: RecommendContext) -> dict[str, float]:
    ...
```

- 입력: `RecommendContext`
- 출력: `P_vec` – Vector 기반 카테고리 score 딕셔너리.

### 5.2 입력에서 사용하는 필드

- `context_full` 또는 그 임베딩 값 (Phase 1 Step 1에서는 임베딩/검색은 Stub 가능)
- `context_hash` – Qdrant/Mongo 등에서 동일 컨텍스트를 찾기 위한 키
- `language`, `field`, `intensity` – 필요 시 feature로 활용 가능

### 5.3 출력 스키마

```jsonc
{
  "thesis": 0.7,
  "email": 0.2,
  "article": 0.1
}
```

- 구조는 P_rule과 동일.
- Phase 1 Step 1에서는
  - Qdrant 검색 대신, 임의/균등/간단한 룰로 score를 생성해도 된다.
  - 단, 실제 P_vec 구현 시에도 이 스키마를 유지해야 한다.

---

## 6. /recommend 내 결합 로직 (P_final)

### 6.1 결합 규칙

Phase 1 Step 1 기준, `/recommend`는 다음과 같이 최종 score를 계산한다.

```python
final_scores: dict[str, float] = {}
for k in set(P_rule) | set(P_vec):
    final_scores[k] = 0.5 * P_rule.get(k, 0.0) + 0.5 * P_vec.get(k, 0.0)

best_category = max(final_scores, key=final_scores.get)
```

- 가중치는 임시로 `0.5 / 0.5`로 두며,
  - 추후 모델팀에서 `macro_weight` 등 추가 파라미터를 설계하면 이 부분만 조정하면 된다.

### 6.2 reco_options 생성 규칙

```jsonc
reco_options = [
  {
    "category": "thesis",
    "language": "ko",        // 요청이 없으면 "ko" 기본값
    "intensity": "moderate"  // 요청이 없으면 "moderate" 기본값
  }
]
```

- Step 1에서는 `best_category` 기준으로 길이 1 리스트만 생성.
- Phase 1.5 이후에는 상위 N개 카테고리를 기반으로
  - 다수 옵션을 만들어 FE에 전달할 수 있다.

---

## 7. 로깅/디버깅 규칙 (A/I/E 이벤트와의 연결)

### 7.1 A 이벤트(editor_recommend_options)와의 관계

- `/recommend`는 P_rule/P_vec를 계산한 후,
  - 해당 값들을 그대로 A 이벤트 payload의 `P_rule`, `P_vec` 필드에 넣어 Kafka + 로그에 남긴다.
- 이때 `context_hash`, `doc_id`, `recommend_session_id`, `insert_id`를 함께 기록하여
  - 나중에 B/C/D/E/K와 조인 가능하게 한다.

### 7.2 I 이벤트(model_score)와의 관계

- I 이벤트는 P_rule, P_vec, (향후) P_doc, P_user, macro_weight 등의
  - “모델 내부 스코어링 정보를 스냅샷으로 남기는” 용도다.
- Phase 1 Step 1에서는
  - 최소한 P_rule, P_vec, context_hash, recommend_session_id, source_recommend_event_id를 포함해 발행한다.

### 7.3 E 이벤트(context_block)와의 관계

- E 이벤트는 Vector 모듈(P_vec)이 사용하는 **문맥 블록**을 Qdrant 등에 저장하도록 하는 트리거다.
- Phase 1 Step 1에서는
  - context_full, context_hash, doc_id, embedding_version 정도만 포함해 발행하면 된다.

---

## 8. 요약

- `/recommend` ↔ 모델(P_rule/P_vec) 사이의 인터페이스는
  - `RecommendContext` 입력과
  - `dict[str, float]` 형태의 P_rule/P_vec 출력으로 고정한다.
- Phase 1 Step 1에서는 Stub/Mock 기반으로 구현해도 무방하며,
  - 모델팀이 실제 로직을 제공할 때는 이 인터페이스를 유지한 채 내부 구현만 교체한다.
- 이로 인해
  - FE ↔ `/recommend` ↔ A/B/C/E 스키마는 변화 없이,
  - 모델의 고도화를 독립적으로 진행할 수 있다.

