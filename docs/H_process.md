# H (Training Examples) 데이터 생성 프로세스 상세

이 문서는 **H (`training_examples`)** 데이터셋이 생성되는 전체 라이프사이클과 ETL 파이프라인의 내부 동작 원리를 상세히 기술합니다.

## 1. 데이터 생성 흐름 (User Interaction Flow)

사용자가 에디터에서 상호작용하는 단계별로 로그가 생성되며, 이들이 모여 최종적인 H 데이터가 됩니다.

### Step 1. 추천 요청 (`/recommend`)
사용자가 텍스트를 드래그하여 선택하면 발생합니다.
*   **API 동작:**
    *   문맥을 분석하여 최적의 카테고리(Category)와 강도(Intensity)를 추천합니다.
    *   이때 `P_vec` (유사 문맥 점수)와 `P_rule` (규칙 기반 점수) 등을 계산합니다.
*   **생성되는 로그:**
    *   **A (`editor_recommend_options`):** 추천된 옵션, 당시의 점수(`P_vec`, `P_rule`), 추천 세션 ID.
    *   **I (`recommend_log`):** 모델 내부 디버깅용 메타 데이터.
    *   **E (`context_block`):** 입력된 문장과 앞뒤 문맥(Context). 추후 벡터 DB에 적재되어 `P_vec`의 검색 소스가 됩니다.

### Step 2. 교정 실행 (`/paraphrase`)
사용자가 '실행' 버튼을 눌러 실제 교정(Paraphrasing)을 요청할 때 발생합니다.
*   **API 동작:**
    *   LLM을 호출하여 교정 후보 문장들을 생성합니다.
*   **생성되는 로그:**
    *   **B (`editor_run_paraphrasing`):** 사용자가 실제로 실행한 옵션(카테고리, 강도, 언어 등)과 LLM 응답 시간.

### Step 3. 문장 선택 및 수락 (`Frontend` → `/log`)
사용자가 생성된 후보 문장 중 하나를 클릭하여 본문에 반영할 때 발생합니다. **(ETL의 핵심 트리거)**
*   **Frontend 동작:**
    *   사용자가 결과를 수락(`was_accepted: true`)했음을 서버에 알립니다.
*   **생성되는 로그:**
    *   **C (`editor_selected_paraphrasing`):** 최종 선택된 문장, 수락 여부.
    *   **D (`correction_history`):** `Original Sentence` -> `Corrected Sentence` 쌍으로 구성된 고품질 Ground Truth 데이터.

---

## 2. ETL 파이프라인 동작 원리

`ETL Worker`는 백그라운드에서 주기적으로 돌며 위에서 쌓인 로그들을 하나로 묶습니다.

### 핵심 트리거 (Trigger)
*   **기준:** **C 로그 (`editor_selected_paraphrasing`)**
*   **조건:** `was_accepted: True` 인 항목만 대상이 됩니다. (사용자가 만족하지 않은 결과는 학습 데이터에서 제외)

### 파이프라인 단계 (`run_etl_pipeline`)

1.  **Aggregation (Join):**
    *   수락된 C 로그의 `recommend_session_id`를 키(Key)로 사용하여 관련 로그를 찾습니다.
    *   **Join A:** 당시 어떤 추천을 받았는지 (`reco_options`, `P_vec`).
    *   **Join B:** 어떤 옵션으로 실행했는지 (`target_category`, `intensity`).
    *   **Join D:** 최종 결과물은 무엇인지 (`groundtruth`).
    *   **Join E:** 당시 문맥은 무엇이었는지 (`context_embedding`).

2.  **Validation (Consistency Check):**
    *   **ID 매칭:** A, B, C 로그가 정말 같은 세션에서 발생했는지 검증합니다.
    *   **Time Check:** 추천(A)과 실행(B) 사이의 시간 간격이 너무 길지 않은지(예: 60초 이내) 확인하여, 유효한 상호작용인지 판단합니다.

3.  **Transformation & Load:**
    *   검증을 통과한 데이터를 `TrainingExample` 스키마로 변환합니다.
    *   MongoDB의 **`training_examples` (H)** 컬렉션에 저장(Upsert)합니다.

## 3. 최종 산출물: H (`training_examples`)

이렇게 생성된 H 데이터는 다음과 같은 풍부한 정보를 담고 있어, 추후 모델 학습(Fine-tuning)이나 추천 알고리즘 개선(Re-ranking)에 활용됩니다.

*   **Input:** 문맥 임베딩, 당시 추천 점수(`P_vec`, `P_rule`), 매크로 정보.
*   **Output (Label):** 사용자가 실제로 선택한 카테고리와 강도(Ground Truth).
*   **Quality:** 사용자가 직접 수락(`Accepted`)한 고품질 데이터임이 보장됨.

---

## 4. G (User Profile)와의 관계 (Data Flywheel)

H 데이터 생성 프로세스와 별개로, 사용자 로그(B, C, D)는 **G (User Profile)**를 업데이트하는 데에도 사용됩니다. 이는 시스템이 사용자를 더 잘 이해하고 더 나은 추천을 제공하게 만드는 **선순환(Flywheel)** 구조의 핵심입니다.

*   **H (Training Examples):**
    *   세션 단위의 **정적 스냅샷(Snapshot)**입니다.
    *   "이 문맥에서 이 추천을 했더니 사용자가 좋아했다"는 사실을 기록하여 모델 학습에 사용합니다.
*   **G (User Profile):**
    *   사용자 단위의 **동적 상태(State)**입니다.
    *   `ProfileService`가 주기적으로(또는 트리거에 의해) B, C, D 로그를 집계하여 사용자의 **선호 카테고리**, **선호 강도**, **행동 벡터(Embedding)**를 최신화합니다.

### 선순환 구조 (Virtuous Cycle)
1.  **추천(A):** G에 저장된 사용자 프로필(`preferred_intensity_map` 등)을 참고하여 개인화된 추천(`P_user`)을 제공합니다.
2.  **반응(B/C):** 사용자가 추천에 반응하여 기능을 실행하고 결과를 수락합니다.
3.  **업데이트(G):** 이 반응 로그가 다시 G를 업데이트하여 프로필을 더욱 정교하게 만듭니다.
4.  **향상:** 다음번 추천(A)의 정확도가 높아집니다.
