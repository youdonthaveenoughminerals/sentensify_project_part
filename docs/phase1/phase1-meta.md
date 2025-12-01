# Phase 1 – 기업 스키마 연동 및 이벤트 확장 명세 (추가)

## 0. 문서 목적

- 기업이 이미 운영 중인 **4가지 JSON 데이터(1~4번)**와
- 새로 정의한 **A~K 스키마 + F/G/J 캐시 구조**를 어떻게 연결할지 정리한다.
- 특히 **기업 이벤트 데이터(3번)**의
  - `editor_run_paraphrasing`
  - `editor_selected_paraphrasing`
  를 Phase 1의 **B/C 이벤트**로 확장하는 규칙을 명시한다.

---

## 1. 기업 4가지 데이터와 A~K 스키마 매핑

| 기업 데이터 | 설명 | 권장 저장소 | A~K 스키마 매핑 |
|------------|------|------------|-----------------|
| 1. 사용자별 사용량 데이터 | 유저별 총 사용 횟수 + 최근 실행 날짜 | Mongo `usage_summary` (선택) | 직접 A~K에 대응되지는 않지만, 추후 user_profile(G) 계산 시 feature로 사용 가능 |
| 2. 사용자 클라이언트 데이터 | distinct_id + properties(country, browser, UTM, last_seen 등) | Mongo `client_properties` (선택) | user_profile(G) 확장시, 지리/디바이스/마케팅 특성을 feature로 활용 가능 |
| 3. 이벤트 데이터 | pageview_ad inflow, run_paraphrasing, selected_paraphrasing, editor_* 이벤트 등 전체 이벤트 로그 | Mongo `event_raw` 또는 BigQuery Raw 테이블 | A/B/C/I/E/H의 원천 이벤트 스트림 |
| 4. 문장 교정 기록 데이터 | input_sentence, output_sentences, selected_index 등 텍스트 Ground Truth | Mongo `correction_history` | D(correction_history) 스키마로 1:1 매핑 |

---

## 2. 이벤트 공통 Envelope (기업 3번 데이터)

기업 이벤트 데이터는 **공통 기본 필드 + 이벤트별 특화 필드** 구조를 가진다.

### 2.1 공통 기본 필드 예시

```jsonc
{
  "event": "run_paraphrasing" | "selected_paraphrasing" | "editor_run_paraphrasing" | ...,

  "distinct_id": "string",
  "device_id": "string",
  "user_id": "string | null",
  "insert_id": "string",

  "time": 1730000000,
  "mp_api_timestamp_ms": 1730000000000,
  "mp_processing_time_ms": 20,

  "browser": "Chrome",
  "browser_version": "120.0",
  "os": "Mac OS X",
  "device": "Mac",
  "screen_height": 1080,
  "screen_width": 1920,

  "city": "Seoul",
  "region": "Seoul",
  "mp_country_code": "KR",

  "current_url": "https://sentencify.ai/editor",
  "referrer": "https://google.com",
  "referring_domain": "google.com",
  "initial_referrer": "https://google.com",
  "initial_referring_domain": "google.com",
  "search_engine": "google",

  "lib_version": "2.50.0",
  "mp_api_endpoint": "api.mixpanel.com",
  "mp_lib": "web",
  "mp_loader": "gtm",
  "environment": "production",
  "extension_version": "1.3.0",

  "browser_is_whale": false,
  "browser_type": "desktop",
  "browser_user_agent": "...",
  "browser_is_chrome": true,
  "browser_is_edge": false,

  "is_logged_in": true,
  "email": "user@example.com",
  "name": "nickname"
}
```

이 공통 Envelope를 그대로 유지하되,  
Phase 1의 A/B/C 트랜잭션 정합성을 위해 **추가 필드**를 붙이는 방식으로 확장한다.

---

## 3. B 이벤트: `editor_run_paraphrasing` 확장 (실행 로그)

### 3.1 기존 기업 필드 (요약)

`run_paraphrasing`/`editor_run_paraphrasing` 이벤트에는 이미 아래와 같은 필드가 포함되어 있다.

- AI 처리 관련
  - `llm_name`, `llm_provider`, `llm_version`
  - `maintenance` (교정 강도)
  - `target_language`
  - `tone`, `terminal_word` (삭제된 기능이지만 과거 로그에 존재)
- 사용자 입력
  - `input_sentence_length`
  - `field` (thesis, article, marketing, ...)
- UI/UX
  - `position` (sidepanel, modal, ...)
  - `platform` (desktop 여부)
  - `trigger` (floating_icon, bottom_icon_tab, ...)
- 성능
  - `response_time_ms`, `response_time_seconds`

### 3.2 Phase 1용 확장 필드

Phase 1 아키텍처에서 B 이벤트는 **“실행 로그”**로 정의되며,  
A/C/D와의 연결을 위해 다음 필드가 추가로 필요하다.

```jsonc
{
  "event": "editor_run_paraphrasing",

  // --- 공통 Envelope 필드 생략 ---

  // Phase 1 트랜잭션 정합성용 추가 필드
  "recommend_session_id": "string",          // A에서 생성한 세션 ID
  "source_recommend_event_id": "string",     // A.insert_id (editor_recommend_options의 insert_id)

  "doc_id": "string",                        // 문서 ID
  "context_hash": "string",                  // hash(doc_id + context_full)

  "api_version": "string",
  "schema_version": "string"
}
```

- 생성 시점
  - FE가 `/recommend`를 호출하면, API가 A 이벤트를 생성하고
    - `recommend_session_id`, `insert_id`(=source_recommend_event_id)를 응답으로 내려줌.
  - FE는 이후 `editor_run_paraphrasing` 이벤트를 발행할 때 이 값을 포함.

---

## 4. C 이벤트: `editor_selected_paraphrasing` 확장 (선택 로그)

### 4.1 기존 기업 필드 (요약)

`selected_paraphrasing` / `editor_selected_paraphrasing`에는 아래 필드가 존재한다.

- 선택 관련
  - `index`: 선택된 후보 인덱스(1~N) 또는 0-based index (기업 정의에 맞추어 사용)
  - `selected_sentence_id`
  - `total_paraphrasing_sentence_count`: 동일 문장으로 재실행한 횟수 등

### 4.2 Phase 1용 확장 필드

C 이벤트는 “선택”을 의미하며,  
D(correction_history)와의 연결을 위해 **`correction_history_id`**가 추가된다.

```jsonc
{
  "event": "editor_selected_paraphrasing",

  // --- 공통 Envelope 필드 생략 ---

  // Phase 1 트랜잭션 정합성용 추가 필드
  "recommend_session_id": "string",          // A/B와 동일 값
  "source_recommend_event_id": "string",     // A.insert_id

  "correction_history_id": "string | null",  // D._id (Mongo ObjectId 문자열)

  "doc_id": "string",
  "context_hash": "string",

  "api_version": "string",
  "schema_version": "string"
}
```

- D 연동 규칙
  1. C 이벤트가 수신되면,
     - `correction_history` 컬렉션에 새로운 D 레코드를 생성.
  2. 생성된 D의 `_id`를 `correction_history_id`로 세팅하여 C 이벤트와 연결.
  3. ETL에서
     - C와 D를 `correction_history_id`로 조인하여 학습용 Ground Truth를 구성.

---

## 5. A 이벤트: `editor_recommend_options` 정의 (신규)

기업 스키마에는 없지만, Phase 1 아키텍처에서 A 이벤트는 필수이므로 정의가 필요하다.

### 5.1 역할

- `/recommend` API 호출 시,
  - 입력 컨텍스트 / Rule/Vector 점수 / 최종 후보 리스트 등을 **스냅샷으로 저장**.
- B/C/D/E/I/H 등 나머지 엔티티들의 기준이 되는 “원천 추천 이벤트”.

### 5.2 필드 예시 (논리 스키마)

```jsonc
{
  "event": "editor_recommend_options",

  "insert_id": "string",             // PK, Mixpanel insert_id와 동일하게 설정
  "recommend_session_id": "string",  // B/C에서 공유하는 세션 ID

  "doc_id": "string",
  "context_hash": "string",

  "context_full_preview": "string",  // 선택: context_full 일부 (디버깅용)

  "candidate_categories": ["thesis", "email", "report"],
  "P_rule": { "thesis": 0.8, "email": 0.1, "report": 0.1 },
  "P_vec":  { "thesis": 0.7, "article": 0.2, "report": 0.1 },

  // Phase 1.5 이후
  "P_doc":  { "thesis": 0.9, "report": 0.05, "email": 0.05 },
  "macro_weight": 0.3,
  "cache_hit": true,

  "embedding_version": "v1.0",
  "llm_version": "string | null",

  "api_version": "string",
  "schema_version": "string",
  "created_at": "2025-11-16T12:34:56Z"
}
```

- 저장 위치
  - 실제 운영에서는 BigQuery DWH의 `A_editor_recommend_options` 테이블 권장.
  - 로컬 개발에서는, 필요 시 Mongo `a_recommend_options` 컬렉션에 임시로 저장하는 것도 가능.

---

## 6. A/B/C/D 키 정합성 규칙 (요약)

Phase 1 아키텍처에서 정의한 규칙을,  
기업 스키마 관점에서 다시 요약하면 다음과 같다.

1. **Rule 1 – recommend_session_id**
   - A 생성 시 API에서 생성.
   - B, C 이벤트는 반드시 동일한 `recommend_session_id`를 포함해야 한다.
   - 세션 단위 분석 (한 번의 드래그 → 실행 → 선택)을 위한 논리 ID.

2. **Rule 2 – source_recommend_event_id**
   - `source_recommend_event_id = A.insert_id`
   - B, C 이벤트는 이 값을 FK로 포함하여,
     - “어떤 추천(A)의 결과로 실행/선택되었는지”를 추적.

3. **Rule 3 – correction_history_id**
   - C 이벤트가 트리거가 되어 D(correction_history)를 생성할 때,
     - D._id를 생성 → C.correction_history_id = D._id 로 세팅.
   - B는 `correction_history_id`를 갖지 않는다.
   - ETL에서
     - C와 D를 `correction_history_id`로 조인.

4. **Rule 4 – doc_id 정합성**
   - A/B/C/D/E/K/F/G/J 등 모든 엔티티는 동일 `doc_id`를 가져야 한다.
   - 그렇지 않으면 Macro Context(K/F)와 Micro Context(E)가 꼬인다.

5. **Rule 5 – context_hash**
   - `context_hash = hash(doc_id + context_full)`
   - A/B/C/E에서 동일한 `context_hash`를 공유.
   - E.context_block(VectorDB)와 A/B/C 로그를 연결하는 키.

---

## 7. BigQuery / DWH 설계(요약)

실제 docker-compose.mini 환경에는 BigQuery가 없지만,  
**최종 운영 구조를 고려한 논리 테이블 구성**을 정리한다.

- `A_editor_recommend_options`
  - A 이벤트 저장
- `B_editor_run_paraphrasing`
  - B 이벤트 저장
- `C_editor_selected_paraphrasing`
  - C 이벤트 저장
- `E_context_block_log` (선택)
  - E(context_block) 메타 정보 로그
- `I_recommend_log`
  - 모델 내부 score/weight 로그
- `H_training_examples`
  - A/B/C/D/E/I 조인 결과로 생성된 학습 데이터
- `G_user_profile`
  - H 기반 집계 결과
- `J_cluster_profile`
  - G 기반 클러스터링 결과

---

## 8. 정리

- **기업 스키마를 버리는 것이 아니라**,  
  - 1~4번 JSON을 그대로 유지하면서,
  - Phase 1 아키텍처에서 요구하는 **A~K 스키마/키 규칙을 “확장”으로 얹는 구조**가 자연스럽다.
- docker-compose로 뜨는 Mongo/Qdrant/Redis는
  - Mongo: `correction_history(D)`, `full_document_store(K)` 등
  - Qdrant: `context_block_v1(E)`
  - Redis: LLM 캐시 + F/G/J 캐시
  를 우선 구성하고,
- 기업 이벤트 스키마는
  - `editor_run_paraphrasing` / `editor_selected_paraphrasing`에
    - `recommend_session_id`, `source_recommend_event_id`, `doc_id`, `context_hash`, `correction_history_id` 등을 추가하여
  - Phase 1/2/3 로드맵에서 요구하는 트랜잭션/학습/개인화 구조를 그대로 만족시키면 된다.

