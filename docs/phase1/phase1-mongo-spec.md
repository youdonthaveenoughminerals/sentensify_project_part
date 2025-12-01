# Phase 1 – MongoDB 스키마 명세 (Draft)

## 0. 범위와 목표

이 문서는 **docker-compose.mini.yml**로 구동되는 MongoDB 컨테이너에서,  
Phase 1 및 이후 Phase(1.5/2)를 고려해 **반드시 생성해야 할 컬렉션과 스키마**를 정의한다.

- DB 이름 예시: `sentencify` (환경 변수 또는 설정으로 변경 가능)
- 주요 컬렉션
  - `correction_history` (D 스키마, 기업 4번 JSON 그대로 사용)
  - `full_document_store` (K 스키마, 문서 원본/블록 저장)
  - (선택) `usage_summary`, `client_properties`, `event_raw` (기업 1~3번 JSON 원본 적재용)

---

## 1. DB 및 공통 설정

```yaml
mongo:
  uri: mongodb://mongo:27017
  db_name: sentencify
```

- 애플리케이션 레벨에서 `DB_NAME=sentencify` 로 고정하거나 `.env`에서 관리.
- 모든 컬렉션은 `sentencify` DB 하위에 생성.

---

## 2. `correction_history` 컬렉션 (D 스키마)

### 2.1 목적

- 기업 측 **`4_문장교정기록.json`** 데이터를 그대로 수용하는 **Ground Truth 저장소**.
- Phase 1~4 전체에서, 학습/품질분석/리플레이의 기준이 되는 텍스트 레벨 로그.

### 2.2 소스 매핑

- 소스 파일: `4_문장교정기록.json`
- 대상 컬렉션: `sentencify.correction_history`
- JSON 레코드를 그대로 insert 하되, `_id`는 기존 ObjectId를 유지.

### 2.3 스키마 정의 (논리 모델)

```jsonc
{
  "_id": ObjectId,
  "created_at": ISODate,
  "user": ObjectId | null,
  "field": "none" | "email" | "article" | "thesis" | "report" | "marketing" | "customer_service",
  "intensity": "weak" | "moderate" | "strong",
  "tone": string | null,
  "user_prompt": string,
  "input_sentence": string,
  "output_sentences": string[],
  "selected_index": int | null,
  "hide": bool,
  "models": ObjectId[],
  "operation_type": string
}
```

> **비고**
> - `user`는 로그인 유저의 ObjectId이며, 기업 2번 데이터(`user_id`)와 연결 가능.
> - `selected_index = null` 인 경우, 사용자가 어떤 후보도 선택하지 않고 이탈한 케이스.

### 2.4 인덱스 설계

```javascript
db.correction_history.createIndex({ user: 1, created_at: -1 })
db.correction_history.createIndex({ field: 1, created_at: -1 })
db.correction_history.createIndex({ intensity: 1 })
```

- 유저별 히스토리 조회, 카테고리/강도별 통계 집계를 고려한 최소 인덱스.

---

## 3. `full_document_store` 컬렉션 (K 스키마)

### 3.1 목적

- 문서 단위 Macro Context의 **유일한 원본 저장소**.
- FE가 전송하는 `editor_document_snapshot` 이벤트를 Consumer가 흡수하여,
  - `latest_full_text` / `previous_full_text`
  - `blocks[]` 및 `diff_ratio`
  를 관리한다.

### 3.2 스키마 정의 (v2.2 반영)

```jsonc
{
  "_id": ObjectId,          // Mongo 내부 PK
  "doc_id": string,         // FE에서 생성/전달하는 문서 ID (UUID 등)

  "latest_full_text": string,        // 최신 전체 문서
  "previous_full_text": string,      // 직전 버전 전체 문서 (diff 계산용, 선택적이나 v2.2에서 권장)

  "blocks": [
    {
      "block_id": string,           // 블록 식별자 (예: "p1", "p2", ...)
      "start_offset": int,          // 전체 텍스트 기준 시작 위치 (선택)
      "end_offset": int,            // 전체 텍스트 기준 끝 위치 (선택)
      "text": string                // 블록 텍스트
    }
  ],

  "diff_ratio": number,             // 최근 snapshot 기준 변경 비율 (0.0 ~ 1.0)
  "last_synced_at": ISODate         // 마지막 snapshot 반영 시각
}
```

### 3.3 인덱스 설계

```javascript
db.full_document_store.createIndex({ doc_id: 1 }, { unique: true })
db.full_document_store.createIndex({ last_synced_at: -1 })
```

- `doc_id` 기준 단일 문서 조회가 대부분이므로 Unique Index.
- ETL에서 최근 업데이트 문서만 스캔할 수 있도록 `last_synced_at` 역순 인덱스.

---

## 4. (선택) 기업 원본 데이터용 컬렉션

Phase 1의 핵심 로직에는 직접 사용되지는 않지만,  
**ETL/분석/리그레이드**를 위해 아래 3개 컬렉션을 Mongo에 적재해 두는 것을 권장한다.

### 4.1 `usage_summary` (기업 1번: 사용자별 사용량 데이터)

```jsonc
{
  "_id": ObjectId,
  "count": int,
  "recent_execution_date": ISODate
}
```

- 사용량 기반 세그멘테이션, AB테스트 타겟팅 등에 활용 가능.
- 권장 인덱스:

```javascript
db.usage_summary.createIndex({ recent_execution_date: -1 })
db.usage_summary.createIndex({ count: -1 })
```

### 4.2 `client_properties` (기업 2번: 사용자 클라이언트 데이터)

```jsonc
{
  "distinct_id": string,   // $device:* or ObjectId string
  "properties": {
    // country_code, region, city, timezone, browser, os,
    // initial_referrer, initial_utm_*, last_seen, ...
  }
}
```

- 추후 user_profile(G) 계산 시, 지리/기기/마케팅 채널 특성을 결합할 때 참고용.
- 권장 인덱스:

```javascript
db.client_properties.createIndex({ "properties.last_seen": -1 })
db.client_properties.createIndex({ distinct_id: 1 }, { unique: true })
```

### 4.3 `event_raw` (기업 3번: 이벤트 데이터 전체)

```jsonc
{
  "event": string,          // pageview_ad inflow, editor_run_paraphrasing, ...
  "distinct_id": string,
  "device_id": string,
  "user_id": string | null,
  "insert_id": string,

  "time": number,                   // unix seconds
  "mp_api_timestamp_ms": number,
  "mp_processing_time_ms": number,

  // browser/os/device/screen/... 등 공통 필드
  // run_paraphrasing / selected_paraphrasing / pageview_ad inflow 전용 필드 등
  "properties": { /* 필요 시 래핑해서 넣어도 됨 (설계 선택지) */ }
}
```

- Phase 2에서 BigQuery로 적재해 A/B/C/I/E/H/G를 생성하는 **원천 로그** 역할.
- 권장 인덱스:

```javascript
db.event_raw.createIndex({ event: 1, time: -1 })
db.event_raw.createIndex({ insert_id: 1 }, { unique: true })
db.event_raw.createIndex({ user_id: 1, time: -1 })
```

---

## 5. 초기 데이터 적재 전략 (요약)

1. MongoDB 컨테이너가 올라온 후, `mongo` 셸 또는 스크립트에서 DB 생성은 생략 가능 (컬렉션 생성 시 자동 생성).
2. `correction_history`
   - `4_문장교정기록.json`을 `mongoimport`로 그대로 적재.
3. `full_document_store`
   - 초기에는 빈 컬렉션만 생성해두고, Kafka Consumer(또는 임시 스크립트)가 `editor_document_snapshot` 이벤트를 처리하며 채워나감.
4. `usage_summary`, `client_properties`, `event_raw`
   - 필요 시 각 JSON 파일을 별도 컬렉션으로 적재.
   - ETL/분석/Phase 2 준비 용도로 사용.

---

## 6. 향후 Phase 연동 메모

- Phase 1.5
  - `full_document_store` → ETL → Macro LLM → Redis(F.document_context_cache)에 저장.
- Phase 2
  - Mongo(D, K) + Redis(F) + BigQuery(H, G, J) 간 조인을 통해 학습 데이터/프로필 생성.
- Phase 3
  - user_embeddings, cluster_profile은 Mongo가 아니라 주로 **VectorDB/Redis/DWH** 쪽에서 관리하되,
    필요하면 요약 정보를 Mongo에 캐싱하는 것도 가능 (선택 사항).

