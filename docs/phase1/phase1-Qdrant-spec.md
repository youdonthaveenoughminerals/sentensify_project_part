# Phase 1 – Qdrant 스키마 명세 (Draft)

## 0. 범위와 목표

이 문서는 **docker-compose.mini.yml**로 구동되는 Qdrant 컨테이너에서,  
Phase 1 기준으로 필요한 **Vector Collection 구조(E.context_block)** 를 정의한다.

- VectorDB: Qdrant
- 주 컬렉션: `context_block_v1`
- 용도: Micro Context 기반 추천(`P_vec`) 및 향후 학습용 벡터 풀

> 벡터 차원(`size`)은 사용 예정인 임베딩 모델에 따라 달라지며,  
> 이 문서에서는 `EMBED_DIM`이라는 **설정값**으로 추상화한다.  
> 실제 수치는 모델 확정 후 설정해야 한다. (예: 512 / 768 / 1024 등, **확실하지 않음**)

---

## 1. Qdrant 서비스 설정

docker-compose 환경에서 Qdrant는 보통 아래처럼 노출된다.

```yaml
services:
  qdrant:
    ports:
      - "6333:6333"
```

- API Endpoint: `http://qdrant:6333` (컨테이너 내부), `http://localhost:6333` (호스트)
- 애플리케이션 설정 예시:

```env
QDRANT_HOST=qdrant
QDRANT_PORT=6333
```

---

## 2. 컬렉션: `context_block_v1` (E.context_block)

### 2.1 목적

- `/recommend` API에서 **`context_full` → embedding → KNN 검색**을 수행하는 대상 컬렉션.
- Phase 1
  - Synthetic 예제 문장 + 샘플 로그 기반으로 초기 벡터 풀 구성.
- Phase 2 이후
  - 실제 사용자 로그 기반 `context_block`이 지속적으로 추가되고,
  - Synthetic 벡터의 가중치를 낮추는 Hybrid 전략에 사용.

### 2.2 Collection 생성 파라미터 (예시)

Qdrant HTTP API 기준 예시 (Python SDK로 호출해도 동일):

```jsonc
PUT /collections/context_block_v1
{
  "vectors": {
    "size": EMBED_DIM,          // 예: 768 (임베딩 모델에 따라 설정, 확실하지 않음)
    "distance": "Cosine"
  },
  "optimizers_config": {
    "default_segment_number": 2
  }
}
```

- `distance = "Cosine"`: 문서에서 cosine similarity 기반 점수를 쓰도록 설계했기 때문에 고정.
- `optimizers_config` 등은 기본값 사용 가능. 트래픽/데이터 양이 늘어나면 조정.

### 2.3 Payload(메타데이터) 스키마

각 포인트의 `payload` 구조는 아래와 같이 설계한다.

```jsonc
{
  "context_hash": "string",             // E 스키마의 논리 PK (doc_id + context_full 해시)
  "doc_id": "string",                   // 문서 ID
  "user_id": "string | null",           // 사용자 ID (로그인 사용자의 ObjectId 문자열 등)
  "preview_text": "string",             // context_full 앞부분 일부 (디버깅/검색용)
  "field": "string | null",             // 교정 카테고리 (thesis/article/..., D.field와 일관)
  "intensity": "weak|moderate|strong|null",

  "embedding_version": "string",        // 예: "v1.0"
  "source_type": "synthetic|real",      // Synthetic DB vs 실제 로그 구분
  "created_at": "2025-11-16T12:34:56Z"  // ISO8601 문자열
}
```

- 필수 필드
  - `context_hash`, `doc_id`, `embedding_version`, `source_type`, `created_at`
- 선택 필드 (서비스에서 필요 시 추가)
  - `field`, `intensity`, `user_id`, `preview_text`

### 2.4 예시 포인트 구조

```jsonc
{
  "id": "ctx_000001",         // Qdrant internal 또는 애플리케이션이 생성한 ID
  "vector": [0.01, -0.03, ...],

  "payload": {
    "context_hash": "97adf3c1e5...",
    "doc_id": "doc_1234",
    "user_id": "66bee4dc71fd9eea359b1a9d",
    "preview_text": "평생 트리 상세 페이지 작업이 예상보다 더...",
    "field": "report",
    "intensity": "moderate",
    "embedding_version": "v1.0",
    "source_type": "synthetic",
    "created_at": "2025-11-16T12:34:56Z"
  }
}
```

---

## 3. 검색 규칙 (Phase 1 기준)

### 3.1 Query 스펙 (논리)

- 입력:
  - `query_vector`: `context_full` 임베딩 결과
  - 필터:
    - `embedding_version == "v1.0"`
    - (선택) `field` / `intensity` / `source_type` 필터

- 파라미터:
  - `k`: 상위 몇 개의 후보를 가져올지 (예: 10~50, 실제 값은 실험으로 조정, **추측입니다**)
  - `score_threshold`: 최소 유사도 임계값 (예: 0.3~0.5, **추측입니다**)

### 3.2 HTTP API 예시 (의사코드)

```jsonc
POST /collections/context_block_v1/points/search
{
  "vector": [/* query_vector */],
  "limit": 20,
  "with_payload": true,
  "filter": {
    "must": [
      { "key": "embedding_version", "match": { "value": "v1.0" } }
    ]
  }
}
```

- 애플리케이션 레벨에서:
  - `result.score` 리스트를 기반으로 `P_vec` 계산 로직을 구현.

---

## 4. Seed 데이터 전략 (Phase 1)

1. **Synthetic 예제 문장 셋**을 미리 준비.
   - 각 예제에 대해
     - `context_full`
     - `field`, `intensity` 등의 메타정보를 정의.
2. 임베딩 모델로 벡터를 생성 후,
   - `source_type="synthetic"` 으로 Qdrant에 적재.
3. 실제 사용자 로그(A/B/C/D/E)가 생기면,
   - E.context_block 생성 시 `source_type="real"` 로 추가.
4. Phase 2에서
   - 쿼리 시 `source_type` 별 가중치 조정 또는 필터링을 통해
   - Synthetic → Real 벡터로 서서히 전환.

---

## 5. 향후 Phase 확장 메모

- Phase 2
  - E.context_block는 그대로 유지하되,
  - 새로운 임베딩 모델 도입 시 `embedding_version="v2.0"`으로 구분하여 **Backfill** 수행.
- Phase 3
  - user_embeddings / cluster_embeddings는
    - 별도의 컬렉션(e.g. `user_embedding_v1`, `cluster_embedding_v1`)으로 가져갈 수 있으나,
    - 현 시점에서는 설계만 열어두고 실제 생성은 보류.

