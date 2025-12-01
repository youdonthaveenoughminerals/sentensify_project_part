사용자님의 \*\*"단독 테스트 환경 제공"\*\*과 \*\*"문서화(docs 업데이트) 의무화"\*\*라는 두 가지 대원칙을 완벽하게 숙지했습니다. 이 원칙은 시스템의 안정성을 보장하고, 개발 진행 상황을 투명하게 관리하는 데 필수적입니다.

이 원칙을 반영하여 **Phase 1.5 로드맵**을 다시 정교하게 수립했습니다.

-----

# 🗓️ Phase 1.5: Macro Context Hybrid 상세 로드맵 (TDD & Doc-Driven)

각 단계는 **구현 → 단독 테스트(스크립트) → 통합 → 문서 업데이트** 순으로 진행됩니다.

### **Step 1. Redis 인프라 & Schema F (Macro Cache)**

  * **목표:** Redis 연결 모듈 구축 및 Macro Context 데이터 구조 정의.
  * **구현:** `api/app/redis/client.py`, `api/app/models/macro.py` (Schema F).
  * **단독 테스트:** `scripts/test_step1_redis.py` (Redis 접속, Set/Get, TTL 동작, Pydantic 검증 테스트).
  * **문서화:** `docs/curr_progress.md` (Redis 연동 완료), `docs/phase1.5_test_lists.md` (캐시 동작 테스트 항목).

### **Step 2. Diff Calculation & Schema K (Gatekeeper)**

  * **목표:** 문서 변경 감지 알고리즘 및 원본 저장소 모델링.
  * **구현:** `api/app/utils/diff.py` (Levenshtein 비율 계산), `api/app/mongo/document_store.py` (Schema K).
  * **단독 테스트:** `scripts/test_step2_diff.py` (텍스트 A vs B 입력 시 diff\_ratio 정확도 검증, Mongo 저장 확인).
  * **문서화:** `docs/curr_progress.md` (Diff 로직 구현), `docs/phase1.5_test_lists.md` (Diff 임계값 테스트 항목).

### **Step 3. Macro ETL Service (LLM Analysis)**

  * **목표:** 텍스트 입력 시 LLM을 호출하여 카테고리를 분석하고 Redis에 저장하는 서비스.
  * **구현:** `api/app/services/macro_service.py` (Gemini 호출 및 Redis 저장).
  * **단독 테스트:** `scripts/test_step3_macro_llm.py` (샘플 텍스트 주입 → LLM 응답 파싱 → Redis 저장 여부 확인).
  * **문서화:** `docs/curr_progress.md` (Macro ETL 구현), `docs/phase1.5_test_lists.md` (LLM 분석 정확도 테스트 항목).

### **Step 4. Adaptive Scoring API Integration**

  * **목표:** `/recommend` API에서 Redis를 조회하고 문서 길이에 따라 가중치($\alpha$) 적용.
  * **구현:** `api/app/main.py` 수정 (Adaptive Logic 추가), `recommend_log` 스키마 업데이트.
  * **단독 테스트:** `scripts/test_step4_scoring.py` (Mock 데이터를 사용하여 문서 길이에 따른 P\_final 점수 변화 검증).
  * **문서화:** `docs/curr_progress.md` (Phase 1.5 통합 완료), `docs/phase1.5_test_lists.md` (시나리오 A/B/C 통합 테스트).

-----
