# TODO, WBS

생성 일시: 2025년 11월 16일 오후 3:31
최종 업데이트 시간: 2025년 11월 16일 오후 4:15
상태: 시작 전

---

### Sentencify MVP WBS 상세 설계서 (v1.0)

본 문서는 v2.2 기술 명세서를 기반으로 Phase 1, 1.5, 2 구현에 필요한 모든 설계 TODO 항목을 정의합니다. WBS(Work Breakdown Structure)는 본 문서의 TODO를 기반으로 작성합니다.

---

### 1. 주요 아키텍처 결정 사항 (One-Way Door Decisions)

프로젝트 착수 전, 팀 전체가 반드시 합의하고 변경을 최소화해야 하는 5가지 핵심 아키텍처 결정 사항입니다. 이 결정들은 롤백 비용이 매우 큽니다.

1. **임베딩 모델 전략 (TODO 10)**
    - **결정:** 임베딩 모델(예: `all-MiniLM-L6-v2` vs `text-embedding-3-small`)을 확정합니다. 이는 비용, 속도, 추천 품질(`P_vec`)을 결정하는 가장 근본적인 선택입니다.
    - **정책:** `E`, `M` 스키마에 `embedding_version` 필드를 필수로 포함하며, API 검색 시 쿼리 벡터와 동일한 버전만 필터링합니다.
2. **ETL 전략 (TODO 9): ELT (Extract-Load-Transform) 확정**
    - **결정:** Airflow는 오케스트레이션만 담당합니다. `H(training_examples)` 생성을 위한 모든 무거운 조인(Transform)은 BigQuery 내부에서 SQL로 처리합니다. (Python Pandas 메모리 조인 금지)
3. **LLM 아키텍처 (TODO 3 & 6): 실시간 vs. 배치 분리**
    - **결정 (실시간):** `Paraphrasing LLM (B 이벤트)`은 P99 Latency 보장을 위해 **LLM 응답 캐시(Redis)**를 필수로 구현하며, 엔드포인트(OpenAI vs Vertex/SageMaker)를 확정합니다.
    - **결정 (배치):** `Macro LLM (K→F)`은 긴 문맥 처리를 위해 **`MapReduce` (Chunking → 요약 → 종합) 프롬프트 체인** 아키텍처로 설계합니다.
4. **Ground Truth 트랜잭션 (TODO 8)**
    - **결정:** `D(correction_history)`는 API 서버가 아닌, `C(선택)` 이벤트를 구독하는 별도의 **Kafka Consumer**가 `MongoDB`에 생성합니다.
    - **정책:** 생성 실패 시 재시도(Retry) 또는 **Dead-Letter Queue(DLQ)**로 보내는 정책을 확정합니다. `H` 생성 시 `D`가 없는 `C` 레코드는 학습에서 제외합니다.
5. **VectorDB 스키마 (TODO 4 & 10)**
    - **결정:** VectorDB에는 벡터뿐만 아니라, 검색 필터링에 필수적인 메타데이터(`embedding_version`, `doc_id`, `user_id` 등)를 Payload로 함께 저장합니다.

---

### 2. Phase별 핵심 TODO 리스트 (12개)

12개 TODO를 WBS의 Epic(최상위 작업 단위)으로 간주하고, 개발 우선순위에 맞게 Phase별로 태깅했습니다.

### [Phase 1: MVP - 실시간 경로 구축]

- **TODO 1 [Phase 1] — 프론트 요청 Contract 확정**
    1. **context_full 생성 규칙:** `prev/selected/next` Concat 규칙, `[SEP]` 토큰 정의, `Truncation` 정책 (백엔드 구현) 확정
    2. **Optional 옵션 처리 규칙:** `undefined`일 때 `null` 처리 또는 payload에서 제거 규칙 정의
    3. **doc_id 발생 규칙:** 프론트엔드 UUID 생성 원칙 및 세션/문서 단위 명확화
- **TODO 2 [Phase 1] — 추천 API(Phase 1) Internal Flow 확정**
    1. **임베딩 생성 함수 설계:** `context_full` → `embedding_v1` 반환 함수
    2. **VectorDB 검색 Query Spec:** `embedding_version` 필터링, `k`값, `threshold` 설정
    3. **P_rule 계산 로직:** Rule Engine 함수 설계
    4. **P_vec 계산 로직:** VectorDB 검색 결과 → `P_vec` 점수 변환 함수 설계
    5. **P_final 산출 공식 (Phase 1):** `w_rule * P_rule + w_vec * P_vec` 가중치(`w`) 확정
    6. **Response DTO 최종 정리:** `recommend_session_id`, `insert_id` 포함 최종 JSON 구조
- **TODO 3 [Phase 1] — LLM 호출 구조 확정 (Paraphrasing LLM)**
    1. **LLM 엔드포인트 결정:** (One-Way Door 참고)
    2. **LLM 응답 캐싱 전략:** `(context_hash + intensity + language)` Key 기반 Redis 캐시 설계
    3. **LLM Prompt 포맷 고정:** `System Prompt` 및 `User Prompt` (옵션 삽입 구조) 확정
    4. **Candidate 생성 개수:** (예: 3개)
- **TODO 4 [Phase 1] — `context_block(E)` final spec + 저장 구조 확정**
    1. **`embedding_version`:** 첫 번째 모델 버전(예: `v1.0`) 확정
    2. **`context_hash` 생성 함수:** 해시 알고리즘(예: SHA-256) 확정
    3. **필수/선택 필드 정의:** `nullable` 필드 처리 방안
    4. **VectorDB 저장 기준:** Payload에 `E` 스키마 전체를 저장할지, 필수 메타데이터만 저장할지 확정
- **TODO 8 [Phase 1] — `D(correction_history)` 생성 트랜잭션 정식 정의**
    1. **생성 시점:** `C(editor_selected_paraphrasing)` 이벤트 발생 시 확정
    2. **생성 위치:** Kafka Consumer (별도 서비스) 확정 (One-Way Door 참고)
    3. **C와 D 연결 방식:** `H` 생성 시 `recommend_session_id` (또는 `C.correction_history_id`)로 조인
    4. **Ground Truth 저장 규칙:** `D` 스키마의 `input_sentence`, `output_sentences` 등 저장 규칙 확정
    5. **실패 시나리오:** 재시도(Retry) 및 DLQ 정책 확정 (One-Way Door 참고)
- **TODO 12 [Phase 1] — `docker-compose.mini.yml` (Phase 1용) 구성**
    1. **서비스 구성:** `fastapi`, `mongodb`, `qdrant`
    2. 서비스 간 네트워크 및 환경변수 설정 정의

### [Phase 1.5: 오프라인 파이프라인 (Macro) 구축]

- **TODO 5 [Phase 1.5] — `editor_document_snapshot(K)` 스키마 + 처리 규칙 완성**
    1. **Snapshot 전송 주기:** FE가 `L(editor_document_snapshot)` 이벤트를 Kafka로 전송하는 시점 확정 (예: 10초 Throttling)
    2. **`diff_ratio` 정확한 정의:** 명세서의 `max(...)` 공식을 Kafka Consumer에서 구현할 상세 로직 확정
    3. **K → F invalidation 트리거 정의:** `diff_ratio >= 10%` 규칙 확정
- **TODO 6 [Phase 1.5] — `Macro LLM(P_doc)` How to Implement**
    1. **Chunking 전략:** `K.latest_full_text` 분할 상세 로직
    2. **MapReduce 구조:** (필수) Chunk 요약(Map) → Global 요약(Reduce) 2-step LLM Chain 아키텍처 설계 (One-Way Door 참고)
    3. **비용/횟수 산정:** 문서 1개당 평균 LLM 호출 횟수 및 비용 산정
    4. **P_doc 계산 방식:** `F.macro_category_hint` → `P_doc` 점수 변환 공식화
    5. **Cache 미스 시 Fallback 값:** (예: `P_doc = 0`)
- **TODO 7 [Phase 1.5] — `Macro Cache(F)` 정확한 K-V 구조 확정**
    1. **Key 구조:** (예: `macro_cache:doc_id:xxxxx`)
    2. **Value 구조:** `F` 스키마 전체를 단일 JSON 문자열로 저장
    3. **TTL 정책:** 동적 TTL 구현 vs 1시간 고정 중 결정
    4. **버전 관리:** `macro_llm_version` 필드 포함 설계
- **TODO 12 [Phase 1.5] — `docker-compose.full.yml` (Phase 1.5/2용) 확장**
    1. **서비스 추가:** `kafka`, `redis`, `airflow` (webserver, scheduler, worker)
    2. 서비스 간 네트워크 및 환경변수 설정 정의
    3. **BigQuery/GCS:** 개발용 GCP 프로젝트 서비스 계정(Key) 주입 방식 확정

### [Phase 2: 학습 루프 (ELT) 구축]

- **TODO 9 [Phase 2] — ETL 전체 설계 (ELT 전략)**
    1. **ELT 전략 확정:** Airflow(오케스트레이션) + BigQuery(Transform) (One-Way Door 참고)
    2. **데이터 적재(L) 방식:** `Mongo(D)`, `Redis(F)` → `BigQuery` 임시 테이블 적재 방법론 확정 (예: `MongoToGCSOperator` → `GCSToBigQueryOperator`)
    3. **`training_examples(H)` SQL 생성 규칙:**
        - `A,B,C,I,E,D_temp,F_temp` 조인 SQL 스크립트 작성
        - `consistency_flag` 계산 로직 SQL로 구현
        - Late Arrival(지연 도착) 로그 처리 및 `NULL` 채우기 규칙 정의
    4. **DAG 스케줄링:** (예: Nightly Batch 또는 Hourly)
- **TODO 10 [Phase 2] — 임베딩 모델 전략 확정 (Backfill 정책 포함)**
    1. **임베딩 모델 선택:** (One-Way Door 참고, WBS 1순위 작업)
    2. **Backfill(재계산) 정책:** 모델 `v2.0` 업그레이드 시, 기존 `E`, `M` 벡터를 재계산하는 Airflow DAG 파이프라인 구상
- **TODO 11 [Phase 2] — `user_profile(G)` 집계 로직 확정**
    1. **G 스키마 상세 로직 확정:**
        - `preferred_category_vector`: `was_accepted=true` 가중치 부여 방식
        - `accept_ratio`: (예: 최근 30일 평균)
    2. **Cold-Start 유저 처리:** `G`가 `nil`인 유저를 위한 **"Global Default Profile"** 정의 및 Airflow DAG에 계산 로직 포함

---