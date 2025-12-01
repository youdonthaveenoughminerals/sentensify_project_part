# 📘 Sentencify Phase 1 – 실시간 추천 & 데이터 수집 명세서 (v1.0 Draft)

작성일: 2025-11-17  
범위: **Phase 1 (실시간 추천 + A/B/C/E 체인)**

---

## 1. 목적 및 범위

### 1.1 목적

Phase 1의 목적은 다음 두 가지를 **동시에** 달성하는 것이다.  

1. 사용자가 문장을 드래그/선택했을 때, **실시간으로 추천 옵션(`P_rule` + `P_vec`)**을 제공한다.
2. 그 과정에서 발생하는 모든 이벤트를 **A-B-C-E 체인**으로 수집하여,  
   이후 Phase 1.5/2에서 사용할 **Macro Context, Training Examples, User Profile**을 위한 기반 데이터를 축적한다.

### 1.2 범위

- 포함
  - 웹 에디터(프론트엔드)에서의 문장 선택 / 추천 / 실행 / 적용 플로우
  - FastAPI 기반 추천 API (`POST /recommend`)
  - Kafka, MongoDB, Qdrant, Redis를 포함한 **실시간 경로(Real-time Path)**의 기본 배선
  - A(editor_recommend_options), B(editor_run_paraphrasing), C(editor_selected_paraphrasing),  
    E(context_block), K(editor_document_snapshot) 스키마 설계

- 제외
  - Phase 1.5 Macro LLM(P_doc) 및 Macro Cache(F) 상세 구현
  - Phase 2~4 (학습 파이프라인, 개인화 추천, 서술형 자동화) 구현

---

## 2. 전체 아키텍처 개요

### 2.1 구성 요소

- **Frontend (React/Vite)**
  - 웹 에디터 UI
  - 문장 선택, 옵션 설정, 실행/적용 플로우 담당
- **FastAPI (Backend)**
  - `POST /recommend` 추천 API
  - A 이벤트 / E(context_block) / I(model_score) 생성 및 Kafka/Mongo/Qdrant/Redis 연동
- **Kafka**
  - 실시간 이벤트 스트림
  - 토픽 예시: `editor_recommend_options`, `editor_run_paraphrasing`, `editor_selected_paraphrasing`, `editor_document_snapshot`
- **MongoDB**
  - D(correction_history) 및 일부 레거시/로그 저장소
- **Qdrant**
  - Vector DB (E.context_block 저장 및 검색, P_vec 계산에 사용)
- **Redis**
  - Paraphrasing LLM 응답 캐시 (B 이벤트 컨슈머에서 사용 예정 – Phase 1 준비 단계)

### 2.2 데이터 경로 (요약)

1. 사용자가 문장 드래그 → FE가 `POST /recommend` 호출 (A 입력)  
2. FastAPI가 Rule + Vector를 통해 추천 생성  
   - VectorDB(Qdrant)에서 유사 문맥 검색 → P_vec 계산  
   - Rule Engine으로 P_rule 계산  
   - 최종 P_final 및 reco_options, recommend_session_id, insert_id 생성  
   - A/I/E 레코드 + context_block(E) + model_score(I) 저장
3. 사용자가 옵션을 조정하고 “교정 실행” → B 이벤트 발생
4. (Phase 1) UX용으로는 API에서 직접 LLM 호출 또는 FE mock 사용  
   (정식 구조는 B 컨슈머 + Redis + LLM, Phase 1.5/2와 연계 – 설계상)  
5. 사용자가 실제 후보를 적용하면 C 이벤트 발생  
   - 이후 C 컨슈머가 MongoDB에 D(correction_history)를 생성

---

## 3. Frontend – Backend Contract (Phase 1)

### 3.1 `POST /recommend` (A 이벤트 입력)

#### 3.1.1 요청 (Request)

```jsonc
POST /recommend
Content-Type: application/json

{
  "doc_id": "string",            // FE에서 UUID로 생성 (문서 단위)
  "user_id": "string",           // 로그인 유저 ID 또는 anonymous

  "selected_text": "string",     // 드래그된 문장/문단
  "context_prev": "string",      // 선택 이전 문맥 (optional)
  "context_next": "string",      // 선택 이후 문맥 (optional)

  // 옵션들 (없으면 null 또는 필드 생략 – TODO 1 규칙 따름)
  "field": "string|null",        // email/article/thesis/report/...
  "language": "string|null",     // ko/en/jp/...
  "intensity": "string|null",    // weak/moderate/strong
  "user_prompt": "string|null"   // 서술형 스타일 요청
}
```

#### 3.1.2 응답 (Response)
```jsonc
{
  "insert_id": "string",             // A 이벤트 PK
  "recommend_session_id": "string",  // 세션 단위 ID

  "reco_options": [
    {
      "category": "string",          // 예: thesis/email/...
      "language": "string",          // 예: ko
      "intensity": "string"          // 예: moderate
    }
  ],

  // Phase 1에서는 내부에서만 사용, FE는 로깅용으로만 참조 (선택)
  "P_rule": { "category": "number" },
  "P_vec":  { "category": "number" },

  "model_version": "string",
  "api_version": "string",
  "schema_version": "string",
  "embedding_version": "string"
}
```

#### 3.1.3 Phase 1 Step 1 – 실제 구현 규칙 정리

- **요청 필드 사용 규칙**
  - `doc_id`  
    - FE가 문서 최초 생성 시 `uuid.v4()`로 생성하여 유지.  
  - `user_id`  
    - 로그인 유저 ID, 미로그인 시 `"anonymous"` 또는 임시 ID.  
  - `selected_text`  
    - 드래그된 실제 문자열 그대로 전송.  
  - `context_prev` / `context_next`  
    - FE에서 prev/next 문장을 계산해 문자열로 보낸다.  
    - BE에서는 이를 사용해  
      `context_full = context_prev + "\n" + selected_text + "\n" + context_next`  
      를 조립한다(null/빈 문자열은 자동으로 제외).  
  - `field`  
    - 옵션 패널에서 카테고리가 `none`이 아니고 ON인 경우만 값 전송, 아니면 `null`.  
  - `language` / `intensity`  
    - ON/OFF 스위치가 켜져 있을 때만 값 전송, 아니면 `null`.  
    - `intensity`는 FE 슬라이더(0/1/2)를 `weak/moderate/strong`으로 매핑.  
  - `user_prompt`  
    - 서술형 스타일 요청 텍스트. 입력이 없다면 `null`.

- **응답 필드 FE 사용 방식 (현재 구현 기준)**
  - `insert_id`  
    - A 이벤트의 PK.  
    - FE에서 B/C 이벤트를 로깅할 때 `source_recommend_event_id`로 사용.  
  - `recommend_session_id`  
    - 한 번의 드래그 → 실행 → 선택 플로우를 묶는 세션 ID.  
    - FE에서는 `recommendId` 상태로 유지, B/C 이벤트에 그대로 포함.  
  - `reco_options`  
    - 현재 Step1에서는 길이 1인 배열이지만, 향후 다수 후보를 반환 가능.  
    - FE는 `reco_options[0]`의 `category`/`language`를 기본 값으로 옵션 패널에 세팅.  
  - `P_rule` / `P_vec`  
    - 모델/데이터 팀 디버깅용 점수. Phase 1에서는 FE에서 DebugPanel/로그에만 표시.  
  - `context_hash`  
    - `hash(doc_id + context_full)`로 계산되는 값.  
    - FE에서는 상태로만 저장하여, B/C 이벤트 및 이후 로그/ETL에서 사용할 수 있도록 한다.

#### 3.2 A/B/C 이벤트 JSON 스키마

##### 3.2.1 A. editor_recommend_options
```jsonc
{
  "insert_id": "string",             // PK
  "recommend_session_id": "string",

  "user_id": "string",
  "doc_id": "string",

  "selected_text": "string",
  "context_prev": "string",
  "context_next": "string",

  "reco_category_input": "string",   // 최종 추천 카테고리
  "reco_options": [ /* 후보 옵션 리스트 */ ],

  "P_rule": { "category": "number" },
  "P_vec":  { "category": "number" },

  "model_version": "string",
  "api_version": "string",
  "schema_version": "string",

  "created_at": "datetime",
  "embedding_version": "string"
}
```

#### 3.2.2 B. editor_run_paraphrasing
```jsonc
{
  "source_recommend_event_id": "string",   // A.insert_id
  "recommend_session_id": "string",

  "doc_id": "string",
  "user_id": "string",

  "target_language": "string",
  "target_intensity": "string",
  "target_category": "string",

  "executed_at": "datetime",
  "created_at": "datetime",
  "paraphrase_llm_version": "string"
}
```

#### 3.2.3 C. editor_selected_paraphrasing
```json
{
  "source_recommend_event_id": "string",   // A.insert_id
  "recommend_session_id": "string",

  "user_id": "string",
  "doc_id": "string",

  "selected_option_index": "int|null",
  "was_accepted": "boolean",

  "created_at": "datetime",
  "correction_history_id": "string",
  "paraphrase_llm_version": "string"
}
```

### 4. Frontend 명세 (Phase 1)
4.1 에디터 동작 요약

사용자가 텍스트를 입력 / 수정

특정 구간을 드래그/선택

선택 시:

prev/selected/next 문맥 계산

POST /recommend 호출 → reco_options + IDs 수신

추천 옵션 패널 업데이트

사용자가 옵션(분야/언어/강도/스타일)을 조정

“교정 실행” 버튼 클릭

B 이벤트 로깅

(임시) mockCorrect 또는 LLM 호출

후보 문장 리스트 UI 표시

사용자가 특정 후보를 적용

C 이벤트 로깅

실제 텍스트 변경

4.2 FE 상태 관리

필수 상태 예시:

docId : 문서 단위 UUID

userId : 로그인 유저 ID 또는 anonymous

text : 전체 문서 내용

selection : 선택 구간 (start, end, text)

context : { prev, selected, next }

recommendId : recommend_session_id

recommendInsertId : A.insert_id

recoOptions : 추천 옵션 후보 리스트

options : { field, language, intensity, style_request }

corrected : 선택된 교정문

5. Phase 1 로드맵과 연계된 구현 순서

Phase 1 로드맵(v1.1)에 따라, FE/BE 작업 순서를 정리한다.

Step 0 – 인프라 구축

docker-compose.mini.yml로 FastAPI, Kafka, MongoDB, Qdrant, Redis 구동

Step 1 – 실시간 API 핵심 구현

POST /recommend에서 context_full → embedding_v1 → VectorDB 검색 → P_rule/P_vec 계산

A/I/E 스키마에 맞춰 Mongo/Qdrant에 저장

Step 2 – 프론트 연결

App.jsx에서 /recommend 호출 붙이기 (Selection → A)

B/C 로그 구조 명세에 맞춰 정리 (실제 전송 대상은 Log Gateway API 열릴 때 연결)

Step 3 – P_vec 튜닝 및 Synthetic Vector 제거

학습/튜닝이 진행되더라도 FE – BE Contract는 그대로 유지

Step 4 – 전체 체인 통합 검증

A/B/C/E/K 이벤트가 모두 Kafka에 정상 적재되는지

ETL(Phase 2)에서 A/B/C/D/E/F/J/H를 Join하여 training_examples 생성 가능한지 확인

6. 비기능 요구사항 (NFR)

Latency

/recommend API P95: 300ms 이내 (Phase 1 기준, 추측입니다)

안정성

이벤트 손실은 Kafka/Consumer 레벨 재시도 및 DLQ로 처리

스키마 호환성

api_version / schema_version 필드로 변경 이력 관리

모니터링

추천 요청 수, 성공/실패, P_vec 히트율, reco_accept_ratio 등을 대시보드로 노출 (Phase 2~)

7. 향후 Phase와의 연결점

Phase 1.5

K(editor_document_snapshot) + F(document_context_cache) + Macro LLM(P_doc)로 Macro Context 도입

A 이벤트에 P_doc 및 macro 관련 필드 추가

Phase 2

H(training_examples), G(user_profile) 생성

VectorDB를 real embedding 중심으로 전환

Phase 3

P_user, P_cluster, Strength/Language Predictor 도입

Phase 4

서술형 옵션 자동화 및 고도화된 개인화 추천
