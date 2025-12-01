# Phase 2.5 – ELK Stack 도입 및 관제 고도화 로드맵

> **목표:** 기존 Streamlit 기반의 제한적인 모니터링 환경을 **ELK (Elasticsearch, Logstash, Kibana) Stack**으로 전면 전환하여, 실시간 로그 검색, 트랜잭션 추적(Tracing), BI(Business Intelligence) 환경을 구축한다.
> **핵심 전략:**
> 1. **Raw Logs:** Kafka Consumer Group을 활용한 **병렬 로그 구독**으로 실시간 관제.
> 2. **Golden Data:** ETL이 생성한 고품질 데이터(H)를 MongoDB에서 **주기적으로 수집**하여 비즈니스 지표 시각화.
> 3. **Streamlit 폐기:** 유지보수 비용 절감을 위해 커스텀 대시보드를 제거하고 Kibana로 통합.

---

## 1. 아키텍처 변경 개요

### AS-IS (현재)
*   **Log Flow:** API → Kafka → Python Worker → **MongoDB**
*   **Monitoring:** Streamlit이 MongoDB를 직접 폴링(Polling)하여 시각화.
*   **한계:** 실시간성 부족, 검색 기능 부재, MongoDB 조회 부하, 커스텀 코드 유지보수 비용.

### TO-BE (Phase 2.5)
*   **Log Flow (Two-Track Strategy):**
    1.  **Track A (Real-time Ops):** API → Kafka → **Logstash** → **Elasticsearch** (Raw Logs)
    2.  **Track B (Business Analytics):** MongoDB(H) → **Logstash (JDBC/Mongo)** → **Elasticsearch** (Golden Data)
*   **특징:**
    *   **병렬 구독:** Kafka Consumer Group을 활용하여 운영 DB 부하 없이 실시간 로그 수집.
    *   **고품질 분석:** ETL이 정제한 Golden Dataset(H)을 별도 인덱스로 적재하여 BI 수준의 시각화 구현.
    *   **Full Replacement:** Streamlit 컨테이너를 제거하고 모든 시각화 기능을 Kibana로 일원화.

---

## 2. 단계별 실행 계획 (WBS)

### Step 1: Docker 인프라 구성 및 Streamlit 제거
*   **목표:** ELK Stack 컨테이너 구동 및 레거시 청산.
*   **작업 내용:**
    *   `docker-compose.elk.yml` 작성 (ES, Logstash, Kibana 8.x).
    *   기존 `docker-compose.mini.yml`에서 **`dashboard` (Streamlit) 서비스 제거**.
    *   메모리 최적화 설정 적용.

### Step 2: Logstash 파이프라인 구성 (Dual Pipeline)
*   **목표:** Raw Log와 Golden Data를 각각 처리하는 두 개의 파이프라인 설정.
*   **작업 내용:**
    *   **Pipeline 1 (Raw Logs):** Kafka Input → `sentencify-logs-*` 인덱스. (실시간 장애 대응용)
    *   **Pipeline 2 (Golden Data):** MongoDB Input (Schedule) → `sentencify-golden-*` 인덱스. (비즈니스 분석용)
        *   *Note:* H 데이터 생성(ETL) 완료 시점을 고려하여 스케줄링 설정.

### Step 3: Kibana 대시보드 구축 (Full Migration & Spec 반영)
*   **목표:** 기존 Streamlit 기능을 포함하여 `docs/dashboard_spec.md`의 핵심 지표를 Kibana로 100% 구현.
*   **작업 내용:**
    *   **Ops Dashboard (구 System Map 대체):**
        *   실시간 로그 스트림 (Discover).
        *   에러율, Latency 히스토그램, API QPS (Line/Area Chart).
        *   Macro Queue 적체량 (Metric).
    *   **Biz Dashboard (Golden Data 기반):**
        *   **Funnel Analysis:** View(A) → Run(B) → Accept(C) 전환율.
        *   **Retention:** 사용자별 재방문율 및 코호트 분석 (Heatmap).
        *   **User Segments:** 카테고리별 선호도 분포 (Pie/Donut Chart).
        *   **ROI Metrics:** 비용 절감 효과(자동화 횟수 * 시간/비용 단가) 시각화 (Metric/Gauge).

---

## 3. 필요 리소스 및 제약사항
*   **메모리:** Elasticsearch 구동을 위해 최소 **4GB 이상의 여유 RAM** 필요.
*   **디스크:** 로그 데이터 적재를 위한 Docker Volume 공간 확보.

---

## 4. 검증 계획 (Test Plan)
1.  **실시간성 테스트:** API 호출 직후 Kibana `sentencify-logs`에서 조회가 되는가?
2.  **분석 정합성 테스트:** MongoDB의 `training_examples` 개수와 Kibana `sentencify-golden` 개수가 일치하는가?
3.  **부하 테스트:** 대량 트래픽 발생 시 Logstash가 병목 없이 처리하는가?

---

## ✅ Phase 2 종료 기준 (Monitoring & Analytics)

다음 3가지 파이프라인이 모두 구축되고 검증되면 Phase 2를 종료(Done) 선언한다.

1.  **Raw Logs 수집:** API → Kafka → Logstash → ES 적재 (실시간 관제).
2.  **Golden Dataset 생성:** MongoDB에 쌓인 A~D 로그를 ETL로 정제하여 `training_examples` (H) 생성.
3.  **Golden Dataset 시각화:** H 데이터를 Logstash가 주기적으로 ES로 쏘고, Kibana에서 비즈니스 지표(정확도, 만족도, ROI 등) 시각화.

> 이 작업이 완료되면, 시스템은 "데이터 수집 -> 정제 -> 시각화"의 완전한 데이터 휠(Data Wheel) 파이프라인을 갖추게 된다.

## 🚀 Next Step: Phase 3 (Personalization)

1.  **기업 데이터(D) Import:**
    *   `docs/기업명세.md`에 정의된 실제 기업 데이터를 MongoDB에 부어넣는다.
    *   Phase 2 파이프라인이 대량의 실제 데이터에서도 잘 작동하는지 검증하는 "실전 테스트" 역할을 겸한다.
2.  **Personalization (개인화):**
    *   사용자 프로필(G)과 클러스터 프로필(J)을 활용하여 추천 점수($P_{user}, P_{cluster}$)를 계산.
    *   개인화된 맞춤 추천 로직 구현 및 API 반영.
