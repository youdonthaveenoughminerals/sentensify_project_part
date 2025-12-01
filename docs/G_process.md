네, 아키텍처가 **Stateful (백엔드 저장 중심)**로 변경되고, 임베딩 생성 시점 최적화가 반영된 G_process.md의 최종 수정본입니다.

이 내용을 프로젝트 문서로 업데이트하시면 됩니다.

G (User Profile) 데이터 생성 프로세스 상세 (v2.4 Revised)
이 문서는 사용자 개인화 추천의 핵심인 G (User Profile) 데이터가 생성되고 업데이트되는 과정을 기술합니다. v2.4부터는 데이터 무결성과 시스템 성능을 위해 Stateful 파이프라인과 Pre-calculated Embedding 방식을 따릅니다.

1. 개요 (Overview)
**G (User Profile)**는 사용자의 선호도(Preference), 행동 패턴(Behavior), **성향(Embedding)**을 집약한 동적 상태(State) 데이터입니다. 이 데이터는 실시간 추천 시스템(P_user)의 직접적인 입력값이며, 유사 유저 검색(P_cluster)의 기준점(Anchor)이 됩니다.

저장 위치: MongoDB user_profile 컬렉션

업데이트 주체: ProfileService (Phase C 종료 직후 즉시 트리거)

참조 로직: Cold Start(데이터 없음)에 대한 예외 처리가 포함되어야 함.

2. 데이터 소스 (Source Logs & Data)
사용자의 상호작용 로그(A, B, C)와 그 결과물인 데이터(D)가 G를 만드는 재료가 됩니다.

단계	로그/데이터 (Schema)	역할 및 G 생성 기여도
A	
editor_recommend_options


(View)

• total_recommend_count: 사용자에게 추천 노출 횟수 집계.
B	
editor_run_paraphrasing


(Generation)

• paraphrase_execution_count: 총 실행 횟수.


• preferred_category_map: 사용자가 실행한 카테고리(Field) 비율.


• preferred_intensity_map: 사용자가 실행한 강도(Maintenance) 비율.


• Note: 이 단계에서 D(Correction History)가 생성(Insert)됨 (Candidate 저장).

C	
editor_selected_paraphrasing


(Selection)

• total_accept_count: 총 수락 횟수.


• overall_accept_rate: 실행 대비 수락률 (만족도 지표).


• Note: 이 단계에서 D가 업데이트(Update)되며, 임베딩이 생성됨.

D	
correction_history


(Vector Source)

• user_embedding_v1: 사용자의 문체/관심사를 나타내는 대표 벡터의 원천 데이터.


• context_embedding 필드(768-dim)를 직접 참조함.


Sheets로 내보내기

3. 생성 및 업데이트 로직 (Aggregation Logic)
ProfileService.update_user_profile(user_id) 메서드는 실시간성과 연산 효율성을 위해 다음과 같은 단계로 G 데이터를 산출합니다.

Step 1. Overview Stats (기본 통계)
집계 대상: A, B, C 로그 컬렉션.

로직: 단순히 각 컬렉션에서 user_id 기준 문서 개수(Count)를 셉니다.

accept_rate = C.count / B.count (단, 분모가 0일 경우 0 처리)

Step 2. Preferences (선호도 분석)
Target: B 로그 (editor_run_paraphrasing)

분석: 사용자가 실행 시 선택했던 옵션(target_category, target_intensity)의 빈도(Frequency)를 계산합니다.

정규화: 전체 실행 횟수로 나누어 비율(Ratio, 0.0~1.0) 형태의 Map으로 변환합니다.

예: {"thesis": 0.8, "email": 0.2}

Cold Start: 데이터가 없으면 빈 dict {}로 초기화.

Step 3. User Embedding (행동 벡터) - [Optimized]
Target: D 데이터 (correction_history)

조건: user_id 일치 AND vector_synced: true (임베딩 생성이 완료된 데이터만)

최적화 로직:

NO Model Inference: 이 단계에서는 무거운 임베딩 모델을 돌리지 않습니다.

Fetch & Average: DB에 이미 저장된 context_embedding (List[float]) 필드를 가져옵니다.

Mean Pooling: 가져온 모든 벡터들의 **평균(Element-wise Mean)**을 구합니다.

결과: 사용자의 현재 관심사와 문체 성향을 대표하는 하나의 벡터(user_embedding_v1)가 생성됩니다.

4. 활용 (Usage)
생성된 G 데이터는 다음과 같이 활용됩니다.

실시간 추천 (P 
user
​
 ):

/recommend 요청 시 preferred_intensity_map을 조회하여, 사용자가 평소 선호하는 강도(예: Strong)에 가중치를 부여합니다.

유사 유저 검색 (P 
cluster
​
 ):

user_embedding_v1 벡터를 Query로 사용하여 Qdrant의 user_behavior 컬렉션을 검색, 유사한 성향을 가진 다른 유저들의 선택 정보를 가져옵니다.

개인화 대시보드:

사용자의 활용 패턴(수락률, 선호 카테고리 등)을 시각화하는 지표로 사용됩니다.

✅ 주요 변경 사항 (v2.4)
임베딩 소스 변경: 실시간 계산 대신 D(correction_history)에 저장된 벡터를 재사용하여 성능 최적화.

데이터 흐름 명시: B단계 생성(Insert) -> C단계 확정(Update) -> G단계 반영(Trigger)의 순서 확립.

벡터 동기화 플래그: vector_synced: true인 데이터만 프로필 생성에 활용하여 데이터 정합성 보장.