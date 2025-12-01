# Sentencify MVP Roadmap & TODO (v2.4)

> **Update (2025-11-25):** 
> - **Phase 2.5 (ELK):** Streamlit을 폐기하고 ELK Stack으로 관제/분석 일원화 진행 중.
> - **Phase 3 (Personalization):** `Airflow` 대신 경량화된 `Prefect` 도입 및 기업 데이터(`user_prompt`) 기반의 정교한 시뮬레이터 구축 예정.

### 1. 🚀 Upcoming Features
*   **✅ H Data Generation (ETL):** Raw Logs(A, B, C)와 Ground Truth(D)를 결합하여 `training_examples` 컬렉션을 생성하는 파이프라인 구현.
*   **✅ H Data Visualization:** 대시보드(Streamlit/ELK)에서 생성된 H 데이터의 분포와 품질을 시각화하는 기능 추가.

---

2. 유저 업데이트 업서트 구현

3. 유저 군 분류하는 ETL 코드 구현
4. H 생성하는 ETL 코드 구현
