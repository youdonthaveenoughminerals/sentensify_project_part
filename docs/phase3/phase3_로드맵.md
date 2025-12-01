# 🚀 Phase 3: Personalization & MLOps (v3.0)

**목표:** 
기업 데이터에서 추출한 **페르소나(Persona)**들이 시스템을 **실제로 사용(Simulation)**하게 하여 살아있는 로그를 쌓고, 이를 통해 **User Profile(G)**과 **Cluster(J)**를 구축하여 초개인화 추천을 완성한다.

---

## 📅 일정 및 마일스톤

| Step | 주제 | 주요 목표 | 예상 기간 |
| :--- | :--- | :--- | :--- |
| **Step 1** | **Persona Mining** | 기업 로그(D)를 분석하여 5~10종의 사용자 페르소나(행동 패턴) 정의 | 1일 |
| **Step 2** | **Traffic Simulation** | 페르소나 봇이 API를 직접 호출하여 A→B→C 흐름의 **Real Log** 적재 | 2일 |
| **Step 3** | **User Personalization ($P_{user}$)** | 시뮬레이션으로 쌓인 로그를 바탕으로 User Profile(G) 생성 및 점수 반영 | 2일 |
| **Step 4** | **Clustering ($P_{cluster}$)** | User Profile 기반 군집화 수행 및 Cold Start용 클러스터 추천 적용 | 2일 |
| **Step 5** | **Automated Pipeline** | 이 모든 과정을 Prefect로 자동화 (Simulate → Profile → Cluster) | 2일 |

---

## 📝 상세 태스크 (Tasks)

### 🟦 Step 1: Persona Mining (from Corporate Data)
> **Goal:** 기업 데이터(Raw)를 분석하여, 시뮬레이터가 연기할 "배역(Persona)"을 짠다.

- [ ] **Raw Data Loader**
    - 기업 제공 JSON(D, Event Raw)을 MongoDB `raw_corporate_data` 컬렉션에 그대로 적재.
    - *Note: 이 데이터는 시스템 로직에 직접 개입하지 않고, 분석용으로만 사용됨.*
- [ ] **Persona Analyzer (`scripts/analyze_persona.py`)**
    - 기업 데이터를 집계하여 주요 사용자 그룹의 특징 추출.
    - **Output:** `personas.json`
      ```json
      [
        {
          "name": "Academic_Writer",
          "preferred_category": "thesis",
          "preferred_intensity": "strong",
          "style_prompt": "학술적인 톤으로 변경해줘",
          "accept_rate": 0.8
        },
        {
          "name": "Casual_Mailer",
          "preferred_category": "email", ...
        }
      ]
      ```

### 🟦 Step 2: Traffic Simulation (Real Flow Injection)
> **Goal:** 페르소나가 API를 실제로 호출하여, 우리 스키마(A/B/C)에 맞는 정합성 높은 데이터를 쌓는다.

- [ ] **Simulator Upgrade (`scripts/generate_persona_traffic.py`)**
    - `personas.json`을 로드하여 각 페르소나별로 봇 생성.
    - **Action Loop:**
        1.  문서 작성 (임의 텍스트).
        2.  `/recommend` 호출 (A 생성).
        3.  페르소나 성향에 따라 옵션 선택 또는 `/paraphrase` 실행 (B 생성).
        4.  최종 선택 및 수락 (C 생성).
- [ ] **Massive Log Injection**
    - 시뮬레이터를 돌려 약 1,000건 이상의 세션 로그 확보.

### 🟦 Step 3: User Personalization Logic ($P_{user}$)
> **Goal:** 시뮬레이션 데이터로 만들어진 Profile을 통해, "나를 알아보는" 추천을 구현한다.

- [ ] **Profile ETL Execution**
    - Phase 2의 `ProfileService`를 실행하여, 시뮬레이션 로그(A/B/C) → `User Profile (G)` 변환.
- [ ] **Scoring Logic Update (`/recommend`)**
    - `api/app/main.py`: Redis에서 G 조회.
    - $P_{user}$ 계산: `CosineSimilarity(ContextVector, UserPreferredVector)`.
    - $P_{final} = (1-\alpha-\beta)P_{vec} + \alpha P_{doc} + \beta P_{user}$ 적용.

### 🟦 Step 4: Clustering & Group Intelligence ($P_{cluster}$)
> **Goal:** 유저들을 그룹핑하여, 데이터가 부족할 때도 "비슷한 그룹"의 취향을 추천한다.

- [ ] **Clustering Service (`api/app/services/cluster_service.py`)**
    - Input: `User Profile (G)`의 `User Embedding V1`.
    - Algo: K-Means (k=5~10, Scikit-learn).
    - Output: `Cluster Profile (J)` 생성 및 Redis 저장 (`cluster_profile:{cluster_id}`).
    - User 정보에 `cluster_id` 매핑 업데이트.
- [ ] **Hybrid Recommendation**
    - `/recommend`에서 User Profile이 없거나 빈약할 경우, $P_{cluster}$ 점수 활용.

### 🟦 Step 5: MLOps Automation (Prefect)
> **Goal:** "분석 → 연기(Simulation) → 학습 → 배포"의 과정을 자동화한다.

- [ ] **Infrastructure Setup**
    - `docker-compose.mini.yml`에 Prefect 추가.
- [ ] **Daily Wheel Flow (`pipelines/daily_simulation.py`)**
    - **Flow:**
        1.  `Simulate`: 페르소나 봇이 트래픽 생성.
        2.  `ETL`: 로그 집계 → Training Data(H) 생성.
        3.  `Profile`: 로그 집계(A/B/C) → User Profile(G) 갱신.
        4.  `Cluster`: G → Clustering → Cluster Profile(J) 갱신.
        5.  `Sync`: Golden Data → ES 적재 (대시보드용).

---

## ✅ 완료 조건 (Exit Criteria)

1.  **시뮬레이터**가 우리 API를 호출하여 A/B/C 로그가 DB에 정상적으로 쌓인다.
2.  쌓인 로그를 바탕으로 **User Profile**과 **Cluster Profile**이 생성된다.
3.  `/recommend` 호출 시, 특정 페르소나(예: 학술 작가)에게 **그 성향에 맞는 옵션이 상위에 추천**된다.
