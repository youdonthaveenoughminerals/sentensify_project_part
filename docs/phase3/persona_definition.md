# Phase 3: Persona Definition & Simulation Strategy

> **작성 목적:** 
> $P_{user}$(개인화)와 $P_{cluster}$(그룹 추천) 알고리즘을 검증하기 위해, **"명확한 취향을 가진 가상의 사용자(Persona)"**들이 실제 데이터(`test_data.csv`)를 사용하여 서비스를 이용하는 시나리오를 정의한다.

---

## 1. 시뮬레이션 데이터 소스 (Input Data)

시뮬레이터는 임의의 문자열이 아닌, 모델 학습/검증에 사용되는 실제 문장을 입력으로 사용한다.

*   **Source:** `api/train_data.csv` (또는 `test_data.csv`)
*   **Mapping:** 페르소나의 `Preferred Category`와 CSV의 `label`이 일치하는 `text`를 랜덤 샘플링하여 사용.
    *   *Example:* **Scholar** 페르소나는 `label=thesis`인 행에서 문장을 가져와 입력한다.

---

## 2. 페르소나 정의 (Persona Profiles)

추천 알고리즘이 학습해야 할 **"핵심 패턴(Ground Truth Pattern)"**을 가진 5가지 페르소나를 정의한다.

### P1. The Academic Perfectionist (학술적 완벽주의자)
*   **주 사용 분야:** `thesis` (90%)
*   **핵심 성향:**
    *   **Intensity:** **Strong** (강력한 교정 선호)
    *   **Language:** `ko` (90%), `en` (10%)
*   **행동 시나리오:**
    *   `thesis` 문장을 입력한다.
    *   시스템이 `Moderate`를 추천하면, **거절하고 `Strong`으로 변경하여 Paraphrase를 실행**한다.
    *   결과가 마음에 들면 선택(Select)한다.
*   **검증 목표:** $P_{cluster}$가 "Thesis 그룹은 Strong을 선호한다"는 규칙을 학습하는지 확인.

### P2. The Global Biz User (해외 영업 담당자)
*   **주 사용 분야:** `email` (80%)
*   **핵심 성향:**
    *   **Intensity:** `Moderate`
    *   **Language:** **English** (100% - 무조건 번역 용도)
*   **행동 시나리오:**
    *   `email` 문장을 입력한다.
    *   시스템이 `ko`를 추천하면, **즉시 `en`으로 변경하여 실행**한다.
*   **검증 목표:** $P_{user}$가 이 사람에게는 문맥과 상관없이 `en`을 우선 추천하는지 확인.

### P3. The Cautious Reporter (보수적인 보고서 작성자)
*   **주 사용 분야:** `report` (80%)
*   **핵심 성향:**
    *   **Intensity:** **Weak** or **Moderate** (원문 유지 선호)
*   **행동 시나리오:**
    *   시스템이 `Strong`을 추천하면 거부감을 느끼고 `Weak`으로 낮춰서 실행한다.

### P4. The Viral Marketer (공격적인 마케터)
*   **주 사용 분야:** `marketing` (70%), `article` (30%)
*   **핵심 성향:**
    *   **Intensity:** **Strong**
*   **행동 시나리오:**
    *   자극적이고 강한 표현을 위해 항상 강도를 높여서 실행한다.

### P5. The Drifter (일반/신규 유저)
*   **주 사용 분야:** Random (`none` 포함)
*   **핵심 성향:** Random (뚜렷한 패턴 없음)
*   **행동 시나리오:**
    *   시스템 추천(`Moderate`)을 대체로 수용하거나, 가끔 이탈한다.
*   **검증 목표:** 데이터가 부족하거나 패턴이 없을 때 $P_{vec}$ 등 문맥 점수가 잘 작동하는지 확인 (Baseline).

---

## 3. 시뮬레이션 로직 (Action Logic)

페르소나 봇(Bot)은 다음 루프를 수행하며 로그를 생성한다.

1.  **Context Injection:**
    *   `test_data.csv`에서 자신의 `Preferred Category`에 맞는 문장을 하나 `Pick`.
2.  **Recommendation Request (A):**
    *   `/recommend` API 호출. (Input: Pick한 문장)
    *   Response: `reco_options` (예: `category=thesis`, `intensity=moderate`, `lang=ko`)
3.  **Decision Making (핵심):**
    *   **Compare:** 추천된 옵션 vs 나의 성향 비교.
    *   **Case 1 (Match):** 추천이 마음에 듦 -> **즉시 선택(Select/C)** (API `/log`).
    *   **Case 2 (Mismatch):** 추천이 마음에 안 듦 -> **옵션 변경 후 실행(Run/B)** (API `/paraphrase`) -> **결과 선택(Select/C)**.
        *   *예:* P1(Scholar)는 `moderate` 추천을 받으면 `strong`으로 바꿔서 실행함.
4.  **Loop:** 위 과정을 반복하여 Session 로그 축적.

---

## 4. 기대 효과 (Expected Outcome)

*   **데이터셋(H)의 품질 향상:** 단순히 쌓인 로그가 아니라, **"추천을 거절하고 수정한 이력"**이 포함되어 학습 가치가 매우 높음.
*   **개인화 검증 가능:** 시뮬레이션 후 P1 유저로 로그인해서 `/recommend`를 했을 때, 초기와 달리 `Strong`이 추천되는지 확인 가능.
