## 1. 지금 상태 체크

### ✅ 이미 끝난 것

- 인프라
    - docker-compose.mini로 **api / frontend / kafka / mongo / qdrant / redis** 6개 서비스 뜨는 구조 완성.
- FastAPI 기본골
    - `POST /recommend` 최소 스켈레톤 존재 (가짜 추천 옵션 + insert_id, recommend_session_id 반환).
- 문서/스펙
    - Phase 1 실행 로드맵(v1.1)
    - Mongo / Qdrant / Redis 스펙
    - meta(트랜잭션 룰: doc_id / context_hash / recommend_session_id / source_recommend_event_id / correction_history_id) 정리 완료.
    - 기업 데이터 명세(1~4 JSON) → A~K 스키마/키 규칙으로 확장 설계 완료.

### ⏳ 아직 안 된 / 반쯤 된 것 (확실)

- `/recommend`가 아직
    - **정식 Request/Response 스키마 적용 전** (doc_id, user_id, context_text, field, intensity 등).
    - **P_rule / P_vec 계산 Stub 없음**.
    - **A / I / E Kafka 이벤트 발행 없음**.
- Kafka Consumer 쪽
    - **B / C / E 컨슈머 코드 없음**.
- Data Layer
    - Mongo에 `correction_history(D)` / `full_document_store(K)` 실제 seed 스크립트 없음 (명세는 있음).
    - Qdrant에 `context_block_v1(E)` 컬렉션/seed 데이터 적재 코드 없음.
    - Redis에 LLM 캐시(F/G/J 네임스페이스 포함) 실제 사용 코드는 없음.
- FE
    - `frontend/src` 내부가 아직 기본 Vite 템플릿 수준이라
        - `/recommend` 호출,
        - B/C 이벤트 발행,
        - insert_id / recommend_session_id 전달
            
            쪽은 **아직 구현 안 된 것으로 보입니다 (확실하지 않음)**.
            

---

## 2. 10개 스펙과 지금 구조의 정합성

**사실 기준으로 보면:**

- 아키텍처 문서의 Real-time Path (FE → API → MQ → E/K/Mongo)와
    
    Phase1 로드맵 v1.1의 Step 1~5, 그리고 meta의 Rule 1~5(IDs)까지 모두,
    
    **서로 모순 없이 일관된 구조**입니다.
    
- Qdrant/Mongo/Redis 스펙도
    - `E.context_block` → Qdrant `context_block_v1`
    - `D.correction_history` → Mongo `correction_history`
    - LLM 캐시 → Redis `llm:paraphrase:{context_hash}:{intensity}:{language}`
        
        로 잘 맞게 설계돼 있음.
        
- 기업 이벤트 스키마(3_이벤트_데이터)도
    - `editor_run_paraphrasing` / `editor_selected_paraphrasing`를
    - `recommend_session_id`, `source_recommend_event_id`, `doc_id`, `context_hash`, `correction_history_id`로 확장하는 방향이 meta 규칙과 정확히 일치.

**즉, “설계상 구조 / 키 규칙 / 이벤트 타입 정의”는 Phase 1 기준에서 이미 맞게 잡혀 있고,
지금부터는 순수하게 “코드 구현”만 채우면 되는 상태**라고 보면 됩니다.

---

## 3. 업데이트된 Phase 1 로드맵 (구현 단위로 쪼갠 버전)

### Step 0 — 인프라 (완료 ✅)

- [x]  Docker Compose로 6개 서비스(api, frontend, kafka, mongo, qdrant, redis) 구동.
- [x]  DevContainer / 로컬 실행 가이드, README 작성.

👉 더 할 일 없음.

---

### Step 1 — `/recommend` API 고도화 (지금 **여기부터** 한다고 보면 됨)

**목표:**

한 번의 `/recommend` 호출로

- 추천 옵션 반환 +
- A / I / E 이벤트를 Kafka에 발행하고,
- doc_id / context_hash / recommend_session_id 규칙을 지키게 만들기.

**구체 작업:**

1. **Pydantic 스키마 정식화**
    - [x]  `RecommendRequest`에 최소 필드 추가  
        - `doc_id: str`
        - `user_id: Optional[str]`
        - `selected_text: str`
        - `context_prev/context_next` (서버에서 `context_full` 조립)
        - `field`, `intensity`, `language`, `user_prompt` 등 옵션.
    - [x]  `RecommendResponse`에
        - `insert_id`, `recommend_session_id`, `options` 배열
        - (선택) `P_rule`, `P_vec` 요약 score 추가.
2. **ID/Hash 생성 로직 구현**
    - [x]  `recommend_session_id` 생성 (uuid4 등).
    - [x]  `insert_id` 생성 (uuid4 기반 Stub).
    - [x]  `context_hash = hash(doc_id + context_full)` 구현 (sha256 등).
3. **P_rule / P_vec Stub**
    - [x]  (Stub) 간단한 딕셔너리 기반 `P_rule` 리턴.
    - [x]  Qdrant를 아직 안 써도 되지만, 인터페이스는
        - `P_vec = {"thesis": 0.5, "report": 0.3, ...}` 형식으로 Stub 구현.
    - 나중에 Step 3에서 실제 Qdrant 검색으로 바꾸기.
4. **Kafka Producer 연동 (A / I / E 이벤트)**
    - [x]  `A_editor_recommend_options` 이벤트 발행
        - payload에 `insert_id`, `recommend_session_id`, `doc_id`, `context_hash`, `P_rule`, `P_vec`, 선택된 `reco_category_input` 포함.
    - [x]  `I_recommend_log` 이벤트 발행
        - 모델 내부 score / weight 로그용 (간단히 P_rule, P_vec, 최종 weight 정도만 먼저).
    - [x]  `E_context_block_log` 또는 `E.context_block`용 이벤트 발행
        - Qdrant에 저장할 `context_full`, `doc_id`, `context_hash`, `field`, `intensity` 등 포함.
5. **환경변수 사용**
    - [x]  `KAFKA_BOOTSTRAP_SERVERS`를 `main.py`에서 실제로 읽어 Kafka Producer 설정에 사용.
    - [ ]  (추가 예정) `MONGO_URI`, `QDRANT_HOST`, `QDRANT_PORT`, `REDIS_HOST`를 컨슈머/헬퍼 코드에서 사용.

---

### Step 2 — Data Layer 준비 (Mongo / Qdrant / Redis)

**목표:**

Phase1이 요구하는 **D, E, K + LLM 캐시**를 로컬에서 다루게 만들기.

1. **Mongo 스크립트**
    - [ ]  `4_문장교정기록.json` → `sentencify.correction_history`로 import (D).
    - [x]  `full_document_store`(K) 컬렉션 생성 + index(doc_id) 생성.  
          → `docker/mongo-init.js`에서 컬렉션 및 인덱스 자동 생성.
    - [ ]  (선택) 기업 1~3 JSON도 `usage_summary`, `client_properties`, `event_raw` 컬렉션에 넣기 (EDA용).
2. **Qdrant 준비**
    - [ ]  Qdrant에 `context_block_v1` 컬렉션 생성 (dim/metric은 임베딩 모델에 맞춰 설정, dim 값은 추측입니다).
    - [ ]  간단한 synthetic context 데이터 몇 개를 임베딩해서 upsert하는 Python 스크립트 작성.
    - [ ]  검색 테스트: query 벡터 하나 던져서 top-k 결과 확인.
3. **Redis 키 네임스페이스**
    - [ ]  LLM 캐시 키 패턴만 먼저 코드에 상수로 정의:
        - `llm:paraphrase:{context_hash}:{intensity}:{language}`
    - [ ]  나중에 B 컨슈머에서 실제로 사용하도록 설계.

---

### Step 3 — FE ↔ BE 계약 구현

**목표:**

프론트에서 실제로 `/recommend`를 호출하고, 그 결과를 기반으로 **B/C 이벤트를 발행**하는 구조를 맞추는 것.

1. **/recommend 호출 연동**
    - [x]  `App.jsx`에 에디터/선택 로직 구현 (textarea + 드래그 기반).
    - [x]  선택 변경 시 `/recommend`로
        - `doc_id`, `user_id`, `selected_text`, `context_prev/next`, `field`, `intensity`, `language` 전송.
    - [x]  응답으로 받은 `insert_id`, `recommend_session_id`, `options`를 상태로 저장.
2. **B 이벤트 발행 (editor_run_paraphrasing)**
    - [ ]  FE에서 실행 버튼을 누른 시점에 B 이벤트 payload 생성:
        - 기업 공통 필드 +
        - `event = "editor_run_paraphrasing"`
        - `recommend_session_id`, `source_recommend_event_id = A.insert_id`, `doc_id`, `context_hash`.
    - [ ]  이 값을 Kafka로 직접 보낼지, 아니면 `/events/b` 같은 API로 보내서 서버에서 Kafka에 넣을지 결정.
3. **C 이벤트 발행 (editor_selected_paraphrasing)**
    - [ ]  사용자가 추천 옵션 중 하나 선택 시 C 이벤트 생성:
        - `event = "editor_selected_paraphrasing"`
        - B와 동일한 `recommend_session_id`, `source_recommend_event_id`
        - `index`, `selected_sentence_id`, `total_paraphrasing_sentence_count`
        - `doc_id`, `context_hash`.
    - [ ]  `correction_history_id`는 아직 null로 두고, 나중에 C 컨슈머에서 세팅.

---

### Step 4 — Kafka Consumers (B / C / E)

**목표:**

이벤트들을 실제로 **Qdrant / Redis / Mongo**로 흘려 보내는 비동기 파이프라인 완성.

1. **E Consumer**
    - [ ]  E 토픽 구독 → `context_full`을 임베딩 → Qdrant `context_block_v1`에 upsert
        - payload 스펙은 `phase1-Qdrant-spec.md` 그대로 사용.
2. **B Consumer**
    - [ ]  B 토픽 구독 → Paraphrasing LLM 호출
    - [ ]  응답 candidate 문장을 Redis 캐시에 저장:
        - key: `llm:paraphrase:{context_hash}:{intensity}:{language}`
    - [ ]  이후 FE가 재실행할 때 API에서 Redis 캐시 탐색하도록 연계 (이 부분은 Step 1 API 고도화와 연결).
3. **C Consumer**
    - [ ]  C 토픽 구독 → `was_accepted == true`인 이벤트만 처리.
    - [ ]  Mongo `correction_history`에 D 문서 insert → 생성된 `_id`를
        - C 이벤트의 `correction_history_id`로 세팅해서 (선택) 별도 로그/테이블에 발행.

---

### Step 5 — E2E 검증 (DoD 체크)

Phase 1 로드맵의 DoD 7개 항목을 실제로 검증하는 단계.

- [ ]  **시나리오 1회 실행**
    - FE에서 문단 드래그 → 추천 버튼 → 후보 중 하나 선택.
- [ ]  아래 모두 확인:
    - `/recommend` 300ms 이내 응답 (Stub 기준에서 충분히 가능).
    - A/I/E 이벤트 Kafka에 존재.
    - E Consumer가 Qdrant에 context 저장.
    - B Consumer가 LLM 호출 → Redis에 캐시 저장.
    - C Consumer가 Mongo에 `correction_history` 생성.
    - FE가 B/C 이벤트에 `insert_id`/`recommend_session_id`를 올바르게 포함.
    - 하나의 세션에서 A → B → C → D → E가 **끊김 없이** 이어지는지 로그로 검증.

---

## 4. 정리

- *설계/스펙은 Phase 1 관점에서 이미 “최종본 수준”**이라, 지금부터는
    - `/recommend`에 A/I/E를 붙이고,
    - Mongo/Qdrant/Redis를 스펙대로 실제로 쓰게 만들고,
    - FE에서 B/C를 쏴주게 만들고,
    - 마지막으로 B/C/E 컨슈머만 묶으면
- 로드맵 v1.1의 DoD 7개 항목을 그대로 만족하는 구조로 끝낼 수 있습니다.

다음 액션으로는 **Step 1의 “/recommend 고도화”부터 잡는 게 제일 자연스러운 순서**고,

그게 끝나면 바로 Step 2(Mongo/Qdrant seed) → Step 3(FE 이벤트) 순서로 밀면 전체 체인이 깔끔하게 맞을 거예요.
