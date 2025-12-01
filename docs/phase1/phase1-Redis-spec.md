# Phase 1 – Redis 스키마 / 키 설계 (Draft)

## 0. 범위와 목표

이 문서는 **docker-compose.mini.yml**로 구동되는 Redis 컨테이너에서,  
Phase 1 및 이후 Phase(1.5/2/3)를 고려한 **Key 네임스페이스와 Value 스키마**를 정의한다.

Redis는 크게 네 가지 용도로 사용된다.

1. **Paraphrasing LLM 응답 캐시** (Phase 1 B 단계)
2. **Macro Context 캐시 F.document_context_cache** (Phase 1.5 이후)
3. **User Profile 캐시 G.user_profile** (Phase 2 이후)
4. **Cluster Profile 캐시 J.cluster_profile** (Phase 3 이후)

---

## 1. 공통 설정

- Redis 호스트: `redis`
- 포트: `6379` (기본값)
- 애플리케이션 설정 예시:

```env
REDIS_HOST=redis
REDIS_PORT=6379
```

네임스페이스 충돌을 막기 위해, 모든 키에 **접두사(prefix)**를 붙인다.

---

## 2. Paraphrasing LLM 응답 캐시 (Phase 1 – B 단계)

### 2.1 용도

- 동일한 `context_full + intensity + language` 조합에 대해,
  - LLM을 매번 호출하지 않고,
  - Redis에서 바로 후보 문장을 읽어오도록 하는 캐시.
- WBS/TODO에서 정의된 키 전략:
  - `(context_hash + intensity + language)` 조합으로 Key 구성.

### 2.2 Key 패턴

```text
llm:paraphrase:{context_hash}:{intensity}:{language}
```

- 예시:
  - `llm:paraphrase:97adf3c1e5...:moderate:ko`
  - `llm:paraphrase:ab12cd34...:strong:en`

### 2.3 Value 스키마 (JSON 직렬화)

```jsonc
{
  "llm_name": "gpt-4.1-mini",
  "llm_provider": "openai",
  "llm_version": "2025-11-01",

  "candidates": [
    "평생 트리 상세 페이지 작업이 예상보다 오래 걸려...",
    "평생 트리 상세 페이지 작업이 예상보다 지연되어...",
    "평생 트리 상세 페이지 작업이 예상보다 더 소요되어..."
  ],

  "created_at": "2025-11-16T12:34:56Z",
  "ttl_seconds": 86400
}
```

- 최소 필수 필드:
  - `candidates`
- 권장 필드:
  - `llm_name`, `llm_version` (디버깅/분석용)
  - `created_at`, `ttl_seconds` (운영 모니터링용)

### 2.4 TTL 정책

- Redis key 자체 TTL: 예시로 **24시간(86400초)** 설정을 추천 (정확한 값은 비용/품질 Trade-off에 따라 조정 필요, **추측입니다**).
- LLM 버전이 바뀌는 경우:
  - `llm_version` 변경 시 기존 캐시를 무시하거나,
  - 버전까지 Key에 포함하는 방식도 선택지:

```text
llm:paraphrase:{llm_version}:{context_hash}:{intensity}:{language}
```

---

## 3. Macro Context 캐시 (F.document_context_cache, Phase 1.5 이후)

### 3.1 용도

- `K.full_document_store`의 `latest_full_text`를 LLM으로 분석한 결과를 캐싱.
- Macro Topic / Macro Category 등을 저장.
- `/recommend` 호출 시 `doc_id` 기준으로 빠르게 조회하여 `P_doc` 계산에 사용.

### 3.2 Key 패턴

```text
macro_cache:{doc_id}
```

- 예시: `macro_cache:doc_1234`

### 3.3 Value 스키마 (JSON 직렬화)

```jsonc
{
  "macro_topic": "startup_funding",
  "macro_category_hint": "report",

  "diff_ratio": 0.08,
  "updated_at": "2025-11-16T12:34:56Z",
  "valid_until": "2025-11-16T13:34:56Z",

  "invalidated_by_diff": false,
  "macro_llm_version": "v1.0"
}
```

- `diff_ratio` / `invalidated_by_diff`는 K 테이블의 diff 계산 결과와 연동.
- 캐시 무효화 규칙 예시
  - `diff_ratio >= 0.10` → 즉시 삭제 및 재생성 예약
  - TTL 만료(`valid_until`) 시 재계산

---

## 4. User Profile 캐시 (G.user_profile, Phase 2 이후)

### 4.1 용도

- ETL에서 계산된 user_profile(G)을 Redis에 캐시하여,
  - `/recommend` 호출 시 **P_user 계산**에 사용.
- `user_id` 기준 조회.

### 4.2 Key 패턴

```text
user_profile:{user_id}
```

- 예시: `user_profile:66bee4dc71fd9eea359b1a9d`

### 4.3 Value 스키마 (JSON 직렬화)

```jsonc
{
  "preferred_category_vector": [0.1, 0.5, 0.2, 0.1, 0.05, 0.05],
  "preferred_strength_vector": [0.2, 0.6, 0.2],
  "preferred_language_vector": [0.8, 0.15, 0.05],

  "recommend_accept_rate": 0.73,

  "user_embedding_v1": [/* 384 or 768 dims */],

  "top_style_requests": ["간결하게", "공손하게"],

  "updated_at": "2025-11-16T10:00:00Z"
}
```

- 벡터 차원(배열 길이)은 Phase 2 설계에서 결정.
- `user_embedding_v1`은 Phase 3의 user_embeddings와 동일한 벡터를 캐시한 값.

---

## 5. Cluster Profile 캐시 (J.cluster_profile, Phase 3 이후)

### 5.1 용도

- 유사 사용자 묶음을 나타내는 `cluster_profile(J)`를 Redis에 캐시.
- `/recommend` 호출 시 `user_profile.cluster_id` → `cluster_profile` 조회 후 **P_cluster 계산**에 사용.

### 5.2 Key 패턴

```text
cluster_profile:{cluster_id}
```

- 예시: `cluster_profile:cluster_001`

### 5.3 Value 스키마 (JSON 직렬화)

```jsonc
{
  "centroid_embedding": [/* 384 or 768 dims */],
  "category_vector": [/* 카테고리별 선호도 */],
  "strength_vector": [/* 강도별 분포 */],
  "language_vector": [/* 언어별 분포 */],

  "last_updated": "2025-11-16T10:00:00Z"
}
```

---

## 6. 네임스페이스 정리 (요약)

| 구분 | Phase | Key Prefix | 예시 키 |
|------|-------|-----------|---------|
| LLM 응답 캐시 | 1 | `llm:paraphrase:` | `llm:paraphrase:ctxHash:moderate:ko` |
| Macro 캐시(F) | 1.5 | `macro_cache:` | `macro_cache:doc_1234` |
| User Profile(G) | 2 | `user_profile:` | `user_profile:66bee4d...` |
| Cluster Profile(J) | 3 | `cluster_profile:` | `cluster_profile:cluster_001` |

---

## 7. 운영 관점 메모

- Redis는 **완전한 Source of Truth가 아닌 캐시 레이어**로 사용한다.
- 모든 값은
  - Mongo/BigQuery/VectorDB 등 **영구 저장소에서 재생성 가능해야 함**.
- 장애/플러시 상황 시,
  - LLM 다시 호출 / ETL 재실행 / DWH 조회 후 재빌드 등의 경로가 확보되어야 한다.

