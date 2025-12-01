죄송합니다. 제가 "Phase 2 집중"이라는 맥락을 과도하게 해석하여, **이미 정의된 Phase 3, 4의 스펙까지 임의로 제외하는 실수를 범했습니다.**

사용자님의 지적대로 \*\*기존에 정의된 [Old Spec]의 모든 지표(Phase 1\~4)\*\*를 유지하면서, \*\*새로 도입된 [New Spec]의 인터랙티브 기능(Topology, Sankey, LLMOps, Demo)\*\*을 통합하는 것이 맞습니다.

이에, **단 하나의 지표도 누락하지 않고**, **데모 시연 기능**까지 포함한 \*\*[최종 완전판 대시보드 명세서]\*\*를 작성해 드립니다.

-----

# 📊 **대시보드 통합 명세서 v2.4 (Final Full Scope)**

  * **적용 아키텍처:** v2.4 (Streamlit Sidecar Pattern)
  * **범위:** **Phase 1 \~ Phase 4 (전체 스펙 포함)**
  * **핵심 컨셉:** **"Interactive Control Tower"** (구조와 흐름 중심의 시각화 + 상세 지표 Inspector)
  * **기술 스택:** `Streamlit`, `streamlit-agraph`, `Plotly`, `pymongo`, `redis-py`

-----

## **1. 레이아웃 및 공통 기능 (Global Layout)**

### **1.1 Sidebar: Live Monitor & Demo Controls**

**목적:** 시스템 생존 확인 및 **데모 시연 통제**.

1.  **System Health (신호등):**
      * MongoDB / Redis / VectorDB 연결 상태 (🟢 Online / 🔴 Offline).
2.  **Demo Controls (시연용 - 신규):**
      * **User ID Filter:** 입력창 (기본값: `All`). 입력 시 모든 차트가 해당 유저 데이터만 쿼리.
      * **Auto-Refresh:** 토글 스위치 (On/Off). On 시 5초 주기 자동 갱신.
3.  **Live Ticker:**
      * 최신 로그 5건 롤링 디스플레이.
      * Format: `[HH:MM:SS] User-123.. : Accepted (320ms)`

### **1.2 Main Pages Navigation**

1.  **🚀 System Topology (Phase 1\~1.5):** 아키텍처 지도, LLMOps, 서비스 안정성 관제.
2.  **💎 Data Flow & Assets (Phase 2):** 데이터 파이프라인 흐름 및 자산화 현황.
3.  **👤 User Insights (Phase 3):** 사용자 프로필 및 군집 분석.
4.  **🤖 Auto-Gen ROI (Phase 4):** 생성형 자동화 성과 분석.

-----

## **2. 페이지별 상세 명세 (Metrics Mapping)**

### **PAGE 0: 🚀 System Topology & LLMOps (Phase 1 & 1.5)**

**목적:** 시스템 구조를 시각화하고, 노드 클릭 시 **기존 Phase 1, 1.5 지표**를 상세 점검한다.

#### **(1) Interactive Topology Map (`streamlit-agraph`)**

  * **Nodes:**
      * 🟦 **Infra:** `User`, `API`, `Worker`, `Mongo`, `Redis`, `VectorDB`
      * 🟪 **AI Models:** `Emb Model` (Sync), `GenAI-Run` (Sync), `GenAI-Macro` (Async)
  * **Edges:** 데이터 흐름 화살표.
  * **Dynamic Activity:** 최근 10초 내 트랜잭션 발생 시 노드 **Green** 점등.

#### **(2) Inspector Panel (하단 클릭 이벤트)**

기존 **Old Spec (Phase 1, 1.5)** 지표를 해당 노드의 Inspector로 이동.

| 클릭 노드 | 포함되는 Old Spec 지표 (Metric) | 시각화 방식 |
| :--- | :--- | :--- |
| **API Server** | • **Total Traffic** (누적 요청 수)<br>• **System Latency** (응답 속도 추이) | Big Number<br>Line Chart |
| **Mongo DB** | • **Category Dist.** (입력 문장 카테고리 분포)<br>• **Drafting vs Polishing** (수정 패턴) | Donut Chart<br>Histogram |
| **Redis** | • **Cache Hit Rate** (캐시 적중률)<br>• **Macro ETL Trigger** (재분석 횟수) | Gauge Chart<br>Bar Chart |
| **GenAI (Macro)** | • **Adaptive Weight ($\alpha$)** (문서 길이별 가중치) | Scatter Plot |
| **Emb Model** | • **Latency (Real-time)** (임베딩 속도) | Metric |
| **GenAI (Run)** | • **Cost Est.** (비용 추정)<br>• **Token Usage** | Metric & Table |

-----

### **PAGE 1: 💎 Data Flow & Assets (Phase 2)**

**목적:** 데이터가 \*\*'학습 데이터(H)'\*\*로 변환되는 과정을 증명.

#### **(1) Pipeline Flow (Sankey Diagram)**

  * **대체:** 기존 `Correction Funnel` (Funnel Chart)를 Sankey로 고도화.
  * **Flow:** `View (A)` → `Run (B)` → `Accept (C)` → `Golden Data (H)`
  * **Insight:** 단계별 이탈률 및 최종 전환율.

#### **(2) Data Asset Metrics (Old Spec 유지)**

  * **Micro Contexts:** 수집된 문장/벡터 자산 규모 (`count(E)`).
  * **Golden Data Count:** 정합성 검증 완료 데이터 수 (`count(H)`).
  * **Acceptance Rate:** 1순위 추천 수용률 (`count(C)/count(A)`).
  * **User Coverage:** 프로필 분석 완료 유저 비율 (`count(G)`).

-----

### **PAGE 2: 👤 User Insights (Phase 3)**

**목적:** 사용자 성향 분석 (Old Spec Phase 3 전체 포함).

#### **(1) User Cluster Map**

  * **지표:** `User Cluster Map` (유저 성향 군집 지도).
  * **Visual:** 2D Scatter Plot (t-SNE of `G.user_embedding`).

#### **(2) Style Analysis**

  * **지표:** `Cluster Tendency` (군집별 선호 스타일).
  * **Visual:** Radar Chart (격식체 vs 구어체 등).

#### **(3) Impact**

  * **지표:** `Personalization Lift` (개인화 적용 전후 수용률 상승폭).
  * **Visual:** Bar Chart.

-----

### **PAGE 3: 🤖 Auto-Gen ROI (Phase 4)**

**목적:** AI 자동화의 비즈니스 임팩트 증명 (Old Spec Phase 4 전체 포함).

#### **(1) Automation Success**

  * **지표:** `Zero-Shot Acceptance` (수정 없이 즉시 수락 비율).
  * **Visual:** Donut Chart.

#### **(2) Efficiency Metrics**

  * **지표:** `Keystrokes Saved` (절약된 타이핑 횟수).
  * **지표:** `ROI / Token Efficiency` (토큰 비용 대비 수용 효과).
  * **Visual:** Big Number, Line Chart.

#### **(3) Trend**

  * **지표:** `Auto-Style Trends` (AI가 제안하는 인기 스타일).
  * **Visual:** Treemap (Word Cloud).

-----

## **3. 구현 가이드 (Directory Structure)**

모든 Phase 페이지를 포함하도록 디렉토리를 구성합니다.

```markdown
sentencify-mvp/
├── dashboard/
│   ├── app.py                  # [Entry] Sidebar Logic (Filter, Refresh) & Navigation
│   ├── pages/
│   │   ├── 0_System_Map.py     # [Page 0] Topology & Inspector (Phase 1, 1.5)
│   │   ├── 1_Data_Flow.py      # [Page 1] Sankey & Assets (Phase 2)
│   │   ├── 2_User_Insights.py  # [Page 2] Cluster & Trends (Phase 3)
│   │   └── 3_Auto_Gen_ROI.py   # [Page 3] Automation Impact (Phase 4)
│   ├── components/
│   │   ├── topology_graph.py   # Agraph Config
│   │   ├── inspector.py        # Inspector Renderer (Metric Charts)
│   │   └── charts.py           # Reusable Plotly Charts (Sankey, Radar, etc.)
│   ├── queries/                # DB Aggregation (Apply User Filter here)
│   ├── requirements.txt        # streamlit-agraph, plotly, pymongo, redis
│   └── Dockerfile
```

### **4. 개발 시 주의사항 (Programmer Instructions)**

1.  **Demo Ready:** `queries/` 내의 모든 함수는 `user_id` 인자를 받아 필터링할 수 있어야 합니다. (데모 시 특정 유저 데이터만 시각화).
2.  **Graceful Degradation:** Phase 3, 4 데이터가 아직 DB에 없더라도 대시보드가 에러를 뱉지 않도록 `try-except` 처리를 하거나, **"Data Pending"** 상태를 표시하십시오. (테이블이 없으면 빈 차트 출력).
3.  **Strict Schema Adherence:** 모든 지표는 앞서 정의된 스키마 `A`\~`L`의 필드만을 사용하여 계산해야 합니다. 새로운 컬럼을 만들지 마십시오.

-----

이 명세서는 사용자님의 \*\*기존 전체 스펙(Phase 1\~4)\*\*을 완벽히 수용하면서, **데모 시연용 기능**과 **인터랙티브 시각화**를 덧입힌 최종 버전입니다.