이 로드맵은 **"데이터가 유실되지 않고 적재되는가?"**에서 시작하여, **"데이터가 가치 있게 가공되는가?"**를 거쳐, **"그 가치가 눈에 보이는가?"**로 끝나는 여정입니다.

---

# 🗓️ Phase 2: Data Accumulation & Dashboard 상세 로드맵

**목표:**
모든 이벤트 로그를 MongoDB에 중앙 집중화하고, 이를 가공하여 학습 데이터(H)와 유저 프로필(G)을 생성한 뒤, 대시보드를 통해 비즈니스 가치를 시각화한다.

---

### **Step 1. Smart Ingester & Log Schemas (Foundation)**
* **목표:** `API`에서 발생한 모든 로그(A~I)를 `Kafka`를 통해 `MongoDB`에 안정적으로(Micro-Batch) 적재한다.
* **작업:**
    * `api/app/schemas/logs.py`: MongoDB용 Pydantic 모델 (`LogA`, `LogB`...) 정의.
    * `api/app/consumer.py`: 모든 토픽 구독 및 `insert_many` 배치 로직 구현.
* **단독 테스트:** `scripts/phase2_test_step1_consumer.py`
    * Mock Kafka로 메시지 150개를 쏘고, MongoDB에 2번(100개, 50개) 나누어 저장되는지 검증.
* **문서화:** `docs/curr_progress.md` (로그 파이프라인 구축), `docs/phase2_test_lists.md`.

### **Step 2. Schema H (Training Examples) & ETL Pipeline**
* **목표:** 흩어진 로그(A, B, C, D, E, F)를 `recommend_session_id`로 조인하여 정답지(H)를 만든다.
* **작업:**
    * `api/app/schemas/training.py`: `TrainingExample` (Schema H) 정의.
    * `api/app/services/etl_service.py`: MongoDB Aggregation Pipeline을 이용한 조인 및 정제 로직 구현.
    * **Consistency Check:** 타임스탬프 차이, 데이터 누락 등을 체크하여 `consistency_flag` 마킹.
* **단독 테스트:** `scripts/phase2_test_step2_etl.py`
    * Mongo에 A, B, C 가짜 로그를 넣고 ETL 함수 실행 후, `training_examples` 컬렉션에 올바른 데이터가 생성되는지 검증.
* **문서화:** `docs/curr_progress.md` (ETL 구현), `docs/phase2_test_lists.md`.

### **Step 3. User Profile (Schema G) Generation**
* **목표:** 사용자의 선택(C) 및 실행(B) 로그를 집계하여 취향 벡터(G)를 생성한다.
* **작업:**
    * `api/app/schemas/profile.py`: `UserProfile` (Schema G) 정의.
    * `api/app/services/profile_service.py`: 유저별 선호 카테고리/강도/언어 카운팅 및 업데이트 로직.
* **단독 테스트:** `scripts/phase2_test_step3_profile.py`
    * 특정 유저의 로그를 넣고 프로필 갱신 실행 시, `preferred_category_vector` 등의 수치가 맞는지 검증.
* **문서화:** `docs/curr_progress.md` (프로필 서비스 구현), `docs/phase2_test_lists.md`.

### **Step 4. Vector DB Migration (Synthetic → Real)**
* **목표:** 가짜 데이터로 돌던 Vector Search를 실제 유저 데이터(H) 기반으로 전환한다.
* **작업:**
    * `api/app/services/vector_migration.py`: `training_examples` 중 `consistency='high'`인 데이터만 Qdrant에 업서트.
* **단독 테스트:** `scripts/phase2_test_step4_migration.py`
    * Mongo(H) 데이터가 Qdrant 컬렉션으로 정확히 전송되는지 확인.
* **문서화:** `docs/curr_progress.md` (Vector 마이그레이션 완료), `docs/phase2_test_lists.md`.

### **Step 5. Analytics Dashboard V1 (Streamlit)**
* **목표:** 데이터 자산 현황과 시스템 상태를 시각화하여 증명한다.
* **작업:**
    * `dashboard/` 폴더 생성 및 `docker-compose` 추가.
    * `dashboard/app.py`: MongoDB/Redis 연결 및 지표(KPI) 쿼리 구현.
    * 프론트엔드 사이드바에 Admin Link 추가.
* **단독 테스트:** (UI 테스트는 스크립트로 어려우므로) 브라우저 접속 테스트 및 주요 쿼리 함수 단위 테스트.
* **문서화:** `docs/curr_progress.md` (Phase 2 완료), `docs/dashboard_spec.md` (구현 반영).

---
