# Sentencify Phase 1 – Current Progress Log

> 진행 상황과 코드/환경 변경사항을 **시간순으로 누적 기록**하는 문서입니다.  
> 새 작업을 할 때마다 이 파일에 아래 포맷으로 항목을 추가합니다.

---

## 2025-11-18 – Phase1 Step1 E2E + Kafka 세팅

### 1. BE `/recommend` API 고도화 (Stub 기반)
- 파일: `api/app/main.py`
- 주요 변경
  - `RecommendRequest`/`RecommendResponse` 정식 스키마 정의
    - Request: `doc_id`, `user_id`, `selected_text`, `context_prev/next`, `field`, `language`, `intensity`, `user_prompt`.
    - Response: `insert_id`, `recommend_session_id`, `reco_options[]`, `P_rule`, `P_vec`, `context_hash`, 버전 정보(`model_version`, `api_version`, `schema_version`, `embedding_version`).
  - `context_full` 조립 및 `context_hash = sha256(doc_id + ":" + context_full)` 구현.
  - Stub 점수:
    - `P_rule = {"thesis": 0.5, "email": 0.3, "article": 0.2}`
    - `P_vec  = {"thesis": 0.7, "email": 0.2, "article": 0.1}
    - `P_final = 0.5 * P_rule + 0.5 * P_vec` 로 최종 카테고리 선택.
  - 추천 옵션 생성:
    - `reco_options = [{ category: best_category, language: req.language or "ko", intensity: req.intensity or "moderate" }]`
  - CORS 허용 추가 (로컬 Vite 프론트에서 직접 호출 가능하도록).

### 2. A / I / E 이벤트 + 파일 로그 + Kafka 연동
- 파일: `api/app/main.py`
- 주요 변경
  - 공통 JSONL 로그:
    - `logs/a.jsonl`, `logs/i.jsonl`, `logs/e.jsonl` 에 이벤트를 한 줄씩 기록하는 `append_jsonl()` 구현.
  - Kafka Producer 초기화:
    - `KAFKA_BOOTSTRAP_SERVERS` 환경변수 사용 (`kafka:9092` 기본값).
    - `get_kafka_producer()`에서 `KafkaProducer` 생성, 실패 시 `None` 반환.
  - 이벤트별 헬퍼:
    - `produce_a_event(payload)` → `editor_recommend_options` 토픽 + `logs/a.jsonl`.
    - `produce_i_event(payload)` → `model_score` 토픽 + `logs/i.jsonl`.
    - `produce_e_event(payload)` → `context_block` 토픽 + `logs/e.jsonl`.
  - `/recommend` 내부에서 한 번의 호출로 A/I/E 이벤트 모두 생성:
    - A: `editor_recommend_options` (입력 컨텍스트 + P_rule/P_vec + reco_options).
    - I: `model_score` (P_rule/P_vec 및 내부 스코어 스냅샷).
    - E: `context_block` (context_full, context_hash, doc_id 중심).

### 3. Frontend ↔ `/recommend` 연동 및 상태 구조
- 파일: `frontend/src/App.jsx`, `frontend/src/utils/api.js`, `frontend/src/DebugPanel.jsx`, `frontend/src/OptionPanel.jsx`
- 주요 변경
  - `axios` 기반 API 클라이언트 추가 (`src/utils/api.js`):
    - `baseURL = VITE_API_BASE_URL || "http://localhost:8000"`
    - `postRecommend(payload)` 헬퍼.
  - 선택 이벤트 → `/recommend` 호출 흐름:
    - `handleSelectionChange`를 `async`로 변경, 드래그 시:
      - 문맥 계산: `context_prev` / `context_next` (문장 단위).
      - intensity 매핑: 슬라이더 0/1/2 → `weak`/`moderate`/`strong`.
      - `/recommend` Request body를 spec에 맞춰 생성 후 `postRecommend` 호출.
    - Response 처리:
      - `recommendId = recommend_session_id`, `recommendInsertId = insert_id` 상태로 저장.
      - `recoOptions`, `contextHash` 상태로 저장.
      - 첫 번째 추천 옵션 기준으로 `category`, `language`를 기본값으로 세팅.
    - FE 로그 (`logEvent`)로 A 이벤트 디버깅용 기록:
      - `event: "editor_recommend_options"` + `P_rule`, `P_vec`, `context_hash`, 버전 정보 포함.
  - B/C 이벤트 쪽 키 정합성 보완:
    - `editor_run_paraphrasing` / `editor_selected_paraphrasing` 로그에
      - `recommend_session_id`, `source_recommend_event_id = insert_id` 포함.

### 4. Docker / Kafka 개발 스택 정리
- 파일: `docker-compose.mini.yml`, `frontend/Dockerfile`
- 주요 변경
  - Kafka 서비스 재구성 (KRaft 단일 노드):
    - `image: apache/kafka:3.7.0`
    - 환경변수:
      - `KAFKA_NODE_ID`, `KAFKA_PROCESS_ROLES`, `KAFKA_LISTENERS`, `KAFKA_ADVERTISED_LISTENERS`,
        `KAFKA_CONTROLLER_LISTENER_NAMES`, `KAFKA_CONTROLLER_QUORUM_VOTERS`,
        `KAFKA_LISTENER_SECURITY_PROTOCOL_MAP`, `KAFKA_LOG_DIRS`, `CLUSTER_ID` 등.
    - 볼륨: `kafka-data:/var/lib/kafka/data`
    - 네트워크: `sentencify-net`
  - API 서비스에서 Kafka 사용:
    - `KAFKA_BOOTSTRAP_SERVERS: "kafka:9092"` 환경변수 유지.
  - Frontend Dockerfile 정리:
    - `node:20-alpine` + `npm ci` 사용.
    - `npm run dev -- --host 0.0.0.0 --port 5173`로 Vite dev 서버 실행.
  - Frontend service command 수정:
    - `docker-compose.mini.yml`에서 `frontend`에
      - `command: sh -c "npm install && npm run dev -- --host 0.0.0.0"` 적용 (컨테이너 내 dev 서버 자동 실행).

### 5. Kafka 토픽 생성 및 확인 (Phase1용)
- Kafka 컨테이너 기동:
  - `docker-compose -f docker-compose.mini.yml up -d kafka`
- 생성한 토픽들:
  - `editor_recommend_options`  (A)
  - `editor_run_paraphrasing`  (B)
  - `editor_selected_paraphrasing` (C)
  - `context_block`            (E)
  - `model_score`              (I)
- 커맨드 예시:
  - 리스트: `kafka-topics --bootstrap-server kafka:9092 --list`
  - 생성: `kafka-topics --bootstrap-server kafka:9092 --create --topic <name> --partitions 3 --replication-factor 1`

### 6. 스펙 문서 정리
- 파일: `docs/phase1/phase1-front-spec.md`
  - 3.1.3에 **“Phase 1 Step 1 – 실제 구현 규칙 정리”** 섹션 추가.
  - FE ↔ `/recommend` 간 필드 사용 규칙 및 응답 활용 방식 정리:
    - `doc_id`, `user_id`, `selected_text`, `context_prev/next`, `field`, `language`, `intensity`, `user_prompt`.
    - `insert_id`, `recommend_session_id`, `reco_options`, `P_rule`, `P_vec`, `context_hash` 등.
- 파일: `docs/phase1/phase1-recommend-spec.md`
  - `/recommend` ↔ P_rule/P_vec 내부 인터페이스 정의:
    - `RecommendContext` 구조,
    - `compute_p_rule(ctx) -> dict[str, float]`,
    - `compute_p_vec(ctx) -> dict[str, float]`,
    - P_final 결합 규칙 및 `reco_options` 생성 규칙,
    - A/I/E 이벤트와의 관계 정리.

### 7. 현재까지 Phase1 Step1 상태 요약
- FE에서 드래그 시 `/recommend` 호출 → Stub 기반 추천 옵션/ID 반환 OK.
- 같은 호출에서 A/I/E 이벤트 생성 → `logs/*.jsonl` + Kafka 토픽까지 적재 OK.
- Kafka 인프라/토픽 구성 완료.
- P_rule/P_vec은 Stub이지만, 인터페이스/스키마/로그 구조는 Phase1 스펙과 정합.
- 다음 단계로는 Mongo/Redis Data Layer 준비 및 B/C 이벤트 엔드포인트/Consumer 구현 예정.

---

## 2025-11-18 – Mongo 초기 스키마 init 스크립트 추가

### 1. Mongo init 스크립트 도입
- 파일: `docker/mongo-init.js`
- 목적:
  - 로컬/팀원 환경에서 MongoDB 컨테이너가 처음 올라올 때,
    Phase1에서 사용하는 컬렉션과 인덱스를 **자동으로 동일하게 생성**하기 위함.
- 주요 내용:
  - DB: `sentencify`
  - 컬렉션 생성 (존재하지 않을 때만):
    - `correction_history`
    - `full_document_store`
    - `usage_summary` (선택)
    - `client_properties` (선택)
    - `event_raw` (선택)
    - `metadata` (init 정보 기록용)
  - 인덱스:
    - `correction_history`:
      - `{ user: 1, created_at: -1 }`
      - `{ field: 1, created_at: -1 }`
      - `{ intensity: 1 }`
    - `full_document_store`:
      - `{ doc_id: 1 }` (unique)
      - `{ last_synced_at: -1 }`
    - `usage_summary`:
      - `{ recent_execution_date: -1 }`
      - `{ count: -1 }`
    - `client_properties`:
      - `{ "properties.last_seen": -1 }`
      - `{ distinct_id: 1 }` (unique)
    - `event_raw`:
      - `{ event: 1, time: -1 }`
      - `{ insert_id: 1 }` (unique)
      - `{ user_id: 1, time: -1 }`
  - `metadata` 컬렉션에 init 기록 1건 insert:
    - `type: "init"`, `source`, `created_at`, `note` 등.

### 2. docker-compose에 init 스크립트 연결
- 파일: `docker-compose.mini.yml`
- 변경 사항:
  - `mongo` 서비스에 init 스크립트 볼륨 마운트 추가:
    ```yaml
    mongo:
      image: mongo:6.0
      ports:
        - "27017:27017"
      volumes:
        - mongo-data:/data/db
        - ./docker/mongo-init.js:/docker-entrypoint-initdb.d/mongo-init.js:ro
      networks:
        - sentencify-net
    ```
- 동작 방식:
  - `mongo-data` 볼륨이 **새로 생성될 때** 컨테이너 기동 시 `mongo-init.js`가 자동 실행된다.
  - 이미 존재하는 `mongo-data` 볼륨이 있으면 init 스크립트는 다시 실행되지 않으므로,
    완전히 초기 상태를 맞추려면 `docker volume rm sentencify-mvp_mongo-data` 후 재기동이 필요하다(주의).

---

## 2025-11-18 – 기업 JSON import용 Mongo 스크립트 및 data 폴더 구조

### 1. 기업 JSON 전용 data 폴더 및 Git 설정
- 파일: `.gitignore`
  - `data/` 항목 추가 → 기업 실제 JSON 데이터는 Git에 올라가지 않도록 설정.
- 폴더:
  - `data/` (프로젝트 루트)
    - 팀원이 각자 로컬에서 기업 제공 JSON 파일을 여기에 복사해서 사용.
    - 예: `data/4_문장교정기록.json` (D.correction_history 원본).

### 2. Mongo 컨테이너에서 data 폴더 접근 설정
- 파일: `docker-compose.mini.yml`
- 변경 사항:
  - `mongo` 서비스에 `./data`를 읽기 전용으로 마운트:
    ```yaml
    mongo:
      image: mongo:6.0
      ports:
        - "27017:27017"
      volumes:
        - mongo-data:/data/db
        - ./docker/mongo-init.js:/docker-entrypoint-initdb.d/mongo-init.js:ro
        - ./data:/data/import:ro
      networks:
        - sentencify-net
    ```
- 효과:
  - 호스트의 `sentencify-mvp/data/*` 파일이 Mongo 컨테이너 내부에서 `/data/import/*` 경로로 보인다.
  - `mongoimport`로 로컬 JSON을 쉽게 import 가능.

### 3. 기업 JSON import 스크립트 추가
- 파일: `scripts/mongo_import_company_data.sh`
- 역할:
  - Phase1에서 사용하는 기업 JSON(D 스키마)을 MongoDB `sentencify.correction_history` 컬렉션에 import.
- 주요 내용:
  - 기본값:
    - `COMPOSE_FILE = docker-compose.mini.yml`
    - `DB_NAME = sentencify`
    - 컨테이너 내부 데이터 경로: `/data/import`
  - 실행 로직:
    ```bash
    docker compose -f "${COMPOSE_FILE}" exec mongo \
      mongoimport \
        --db "${DB_NAME}" \
        --collection correction_history \
        --file "/data/import/4_문장교정기록.json" \
        --jsonArray
    ```
  - 실행 방법:
    ```bash
    cd sentencify-mvp
    chmod +x scripts/mongo_import_company_data.sh  # 최초 1회
    ./scripts/mongo_import_company_data.sh
    ```
- 주의 사항:
  - JSON 파일들은 Git에 포함되지 않으며, 팀원이 각자 `data/import` 폴더에 수동으로 복사해야 한다.
  - 컬렉션에 중복 insert를 방지하려면, 필요 시 `mongoimport` 옵션 또는 사전 정리 로직을 추가하는 것을 고려.

---

## 2025-11-18 – B/C 이벤트 수집용 /log 엔드포인트 추가

### 1. LogRequest 모델 및 /log API
- 파일: `api/app/main.py`
- 추가/변경 사항:
  - `LogRequest` Pydantic 모델 정의:
    - 필드: `event: str`
    - `extra = "allow"` 설정으로 나머지 필드는 자유롭게 허용 (전체 payload를 그대로 보존).
  - `POST /log` 엔드포인트 추가:
    - Body를 `LogRequest`로 수신하고 `req.model_dump()`로 전체 payload를 dict로 변환.
    - `event` 필드 값에 따라 분기:
      - `"editor_run_paraphrasing"` → B 이벤트로 처리.
      - `"editor_selected_paraphrasing"` → C 이벤트로 처리.
      - 그 외 이벤트 → `logs/others.jsonl`에만 기록.

### 2. B/C 이벤트용 프로듀서 헬퍼
- 파일: `api/app/main.py`
- 추가 함수:
  - `produce_b_event(payload: Dict) -> None`
    - `logs/b.jsonl`에 append.
    - Kafka Producer가 활성화되어 있으면 `editor_run_paraphrasing` 토픽으로 send.
    - Kafka 오류 발생 시 예외를 삼키고 흐름 유지.
  - `produce_c_event(payload: Dict) -> None`
    - `logs/c.jsonl`에 append.
    - Kafka Producer가 활성화되어 있으면 `editor_selected_paraphrasing` 토픽으로 send.
    - Kafka 오류 발생 시 동일하게 무시.
- 기존 A/I/E 헬퍼(`produce_a_event`, `produce_i_event`, `produce_e_event`)와 동일한 패턴 유지.

### 3. Kafka 비활성화(KAFKA_ENABLED=false) 처리
- `get_kafka_producer()` 로직을 재사용하여,
  - `KAFKA_ENABLED=false`인 경우 `None`을 반환하며,
  - B/C/A/I/E 모든 `produce_*_event` 함수에서 `producer is None`이면 Kafka 전송을 건너뛰도록 구현.
- 결과:
  - Kafka가 꺼져 있거나 설정이 잘못되더라도 `/recommend` 및 `/log`는 에러 없이 실행되고,
  - 최소한 로컬 파일 로그(`logs/*.jsonl`)는 항상 남도록 보장.

---

## 2025-11-18 – Kafka C/E Consumer 스켈레톤 추가

### 1. consumer.py 생성
- 파일: `api/app/consumer.py`
- 역할:
  - Kafka 토픽에서 C/E 이벤트를 구독하여
    - C: MongoDB `correction_history`에 적재
    - E: Qdrant `context_block_v1`에 upsert
  하는 Phase1용 Consumer 스켈레톤.

### 2. 공통 설정
- 사용 라이브러리:
  - `kafka-python`, `pymongo`, `qdrant-client`
- 환경변수:
  - `KAFKA_BOOTSTRAP_SERVERS` (기본 `kafka:9092`)
  - `MONGO_URI` (기본 `mongodb://mongo:27017`)
  - `MONGO_DB_NAME` (기본 `sentencify`)
  - `QDRANT_HOST` (기본 `qdrant`)
  - `QDRANT_PORT` (기본 `6333`)
  - `EMBED_DIM` (기본 `768`, Stub 벡터 차원)

### 3. C 이벤트 Consumer (`editor_selected_paraphrasing`)
- 함수: `process_c_events()`
- 동작:
  - KafkaConsumer 설정:
    - 토픽: `editor_selected_paraphrasing`
    - `auto_offset_reset="earliest"`, `enable_auto_commit=True`
    - `group_id="sentencify_c_consumer"`
  - 각 메시지에 대해:
    - payload를 dict로 파싱.
    - `was_accepted`가 명시적으로 `false`인 경우는 무시 (실제 채택된 것만 저장).
    - MongoDB `sentencify.correction_history` 컬렉션에 `insert_one`:
      - 전체 payload를 복사하고 `created_at`에 현재 UTC ISO 문자열을 추가.
  - 예외 발생 시:
    - 에러 메시지만 출력하고 루프는 계속.

### 4. E 이벤트 Consumer (`context_block`)
- 함수: `process_e_events()`
- 동작:
  - Qdrant 클라이언트 초기화 후 `ensure_qdrant_collection()` 호출:
    - 컬렉션 이름: `context_block_v1`
    - `VectorParams(size=EMBED_DIM, distance=Cosine)` 로 컬렉션이 없을 경우 생성.
  - KafkaConsumer 설정:
    - 토픽: `context_block`
    - `group_id="sentencify_e_consumer"`
  - 각 메시지에 대해:
    - payload를 메타데이터로 활용.
    - Stub 벡터 생성: `[0.0] * EMBED_DIM`
    - Qdrant `upsert` 호출:
      - `PointStruct(id=str(uuid.uuid4()), vector=vector, payload=payload)` 형태로 등록.
  - 예외 발생 시:
    - 에러 메시지를 출력하고 루프를 계속 진행.

### 5. 실행 구조
- `main()` 함수:
  - 두 개의 데몬 스레드 생성:
    - `process_c_events` / `process_e_events` 각각을 별도 스레드로 실행.
  - 스레드 시작 후 `join()`으로 메인 스레드를 유지.
  - `KeyboardInterrupt` 시에는 메시지만 출력하고 종료.
- 엔트리포인트:
  - `if __name__ == "__main__": main()` 블록을 추가하여
    - `python -m app.consumer` 또는 `python app/consumer.py` 로 직접 실행 가능하도록 구성.

---

## 2025-11-18 – Infra: users 컬렉션 및 인증 의존성 추가

### 1. Mongo users 컬렉션 준비
- 파일: `docker/mongo-init.js`
- 변경 사항:
  - `users` 컬렉션 자동 생성 로직 추가:
    - 컬렉션이 없을 경우 `db.createCollection("users")`.
  - 인덱스:
    - `db.users.createIndex({ email: 1 }, { unique: true })`  
      → 이메일 기준 유저 조회 및 중복 방지용 Unique Index.
- 효과:
  - 새 환경에서 Mongo 컨테이너가 처음 올라올 때,
    `sentencify.users` 컬렉션과 `email` 유니크 인덱스가 자동으로 준비되어,
    이후 회원 관리/인증 기능을 구현할 때 바로 사용할 수 있음.

### 2. API 인증 관련 라이브러리 의존성 추가
- 파일: `api/requirements.txt`
- 추가된 패키지:
  - `python-jose[cryptography]`
    - JWT 발급/검증용 라이브러리.
  - `passlib[bcrypt]`
    - 비밀번호 해싱/검증용 (bcrypt 스키마 사용).
  - `python-multipart`
    - FastAPI에서 form-data 기반 로그인/업로드 등을 처리할 때 필요한 의존성.
- 현재는 실제 인증/회원 엔드포인트는 구현하지 않았으며,
  - Phase1 이후 회원 관리 기능을 붙일 때 사용할 준비 단계로 패키지만 추가한 상태.

---

## 2025-11-18 – Backend: Implemented JWT Auth API (Ready for Frontend)

### 1. Auth 라우터 및 Mongo users 연동
- 파일: `api/app/auth.py`
- 주요 내용:
  - PyMongo 기반 `users` 컬렉션 헬퍼:
    - `get_mongo_users_collection()` → `sentencify.users` 컬렉션 반환.
  - 비밀번호 해싱/검증:
    - `passlib.context.CryptContext` (bcrypt) 사용.
    - `hash_password(password)`, `verify_password(plain, hashed)` 유틸 함수 정의.
  - JWT 토큰 생성:
    - `create_access_token(data, expires_delta)`:
      - 기본 만료 시간: `ACCESS_TOKEN_EXPIRE_HOURS` (환경변수, 기본 24시간).
      - `SECRET_KEY` 환경변수와 `HS256` 알고리즘으로 서명.
  - Pydantic 모델:
    - `SignupRequest`: `email: EmailStr`, `password: str`
    - `LoginRequest`: `email: EmailStr`, `password: str`
    - `TokenResponse`: `access_token`, `token_type="bearer"`

### 2. `/auth/signup` 엔드포인트
- 라우터: `auth_router.post("/signup")`
- 동작:
  - `SignupRequest` 수신 (`email`, `password`).
  - `users.find_one({"email": req.email})`로 중복 이메일 체크:
    - 이미 존재하면 HTTP 400 (`"Email already registered"`).
  - 신규 유저 문서 생성:
    - `email`
    - `password_hash` (bcrypt 해시)
    - `created_at` (UTC ISO 문자열)
  - `insert_one` 후 `{"id": <inserted_id>, "email": ...}` 형태로 응답.

### 3. `/auth/login` 엔드포인트
- 라우터: `auth_router.post("/login")`, `response_model=TokenResponse`
- 동작:
  - `LoginRequest` 수신 (`email`, `password`).
  - 해당 이메일 유저 조회:
    - 없으면 HTTP 400 (`"Invalid credentials"`).
  - bcrypt로 비밀번호 검증:
    - 실패 시 동일하게 HTTP 400 (`"Invalid credentials"`).
  - JWT Access Token 생성:
    - payload: `{"sub": email, "user_id": str(user["_id"])`}. 
    - 만료: 기본 24시간(환경변수로 조정 가능).
  - 응답:
    - `{"access_token": "<JWT>", "token_type": "bearer"}`.

### 4. main.py에 Auth Router 등록
- 파일: `api/app/main.py`
- 변경 사항:
  - `from .auth import auth_router` import 추가.
  - 파일 하단에:
    ```python
    app.include_router(auth_router, prefix="/auth")
    ```
    를 추가하여 `/auth/signup`, `/auth/login` 경로가 메인 FastAPI 앱에 노출되도록 설정.
- 결과:
  - 프론트엔드는 `/auth/signup`, `/auth/login`를 통해
    - 회원 가입 / 로그인 + JWT 발급 플로우를 붙일 수 있는 상태가 되었음.
  - 현재는 보호 라우터/토큰 검증 의존성은 추가하지 않았으며,
    - 이후 필요 시 `Depends` 기반 JWT 검증 유틸을 같은 모듈에 확장 가능.

---

## 2025-11-18 – Frontend: Integrated Real Auth API (Login/Signup)

### 1. AuthContext에서 실제 /auth API 연동
- 파일: `frontend/src/auth/AuthContext.jsx`
- 변경 사항:
  - `../utils/api.js`의 axios 인스턴스(`api`)를 사용하도록 변경.
  - 로컬 스토리지 키:
    - 사용자 정보: `auth:user:v1`
    - 액세스 토큰: `auth:token:v1`
  - 초기화 로직:
    - 마운트 시 localStorage에서 user/token을 읽어 `user` 상태를 복원하고,
      토큰이 있으면 `api.defaults.headers.common.Authorization = "Bearer <token>"` 설정.

### 2. 로그인 / 회원가입 / 로그아웃 구현
- `login({ email, password })`:
  - `POST /auth/login` 호출 → `access_token` 수신.
  - `user = { email }` 상태로 세팅.
  - localStorage에 user/token 저장.
  - axios default header에 `Authorization: Bearer <token>` 설정.
- `signup({ email, password })`:
  - `POST /auth/signup` 호출.
  - 성공 시 `login({ email, password })`를 호출하여 자동 로그인 처리.
- `logout()`:
  - `user` 상태를 `null`로 초기화.
  - localStorage에서 user/token 키 제거.
  - axios default header에서 `Authorization` 제거.

### 3. 효과
- 프론트엔드에서 Mock Auth 대신 실제 FastAPI `/auth/signup`, `/auth/login` API를 사용하여 인증 플로우 구현.
- 이후 보호된 API를 호출할 때 Authorization 헤더를 자동으로 사용할 수 있는 기반이 준비됨.

---

## 2025-11-18 – Frontend UX: Auto-refresh Sidebar on save

### 1. 자동 저장 시 Sidebar 문서 목록 갱신 트리거
- 파일: `frontend/src/App.jsx`, `frontend/src/Sidebar.jsx`
- 변경 사항:
  - `App.jsx`:
    - 상태 추가:
      - `lastSnapshotTime` (최근 자동 저장/스냅샷 시간)
      - `refreshTrigger` (Sidebar 목록 갱신용 카운터)
      - `isSaving` (저장 중 표시용)
    - 자동 저장(useEffect) 로직 보완:
      - 텍스트 변경 시 400ms debounce 후 localStorage에 저장.
      - 저장 직후:
        - `lastSnapshotTime = Date.now()`
        - `refreshTrigger++`
        - `isSaving = false`
      - 효과: 실제 K 이벤트/스냅샷 성공 시점에 맞춰 이 부분만 조정하면, Sidebar가 자동으로 최신 목록을 가져오게 됨.
    - Sidebar에 `refreshTrigger` 전달:
      ```jsx
      <Sidebar
        userId={user?.id}
        refreshTrigger={refreshTrigger}
        ...
      />
      ```
  - `Sidebar.jsx`:
    - `refreshTrigger`를 props로 받아 `useEffect` 의존성에 추가:
      - `useEffect(..., [userId, refreshTrigger])`
      - 값이 바뀔 때마다 `GET /documents?user_id=...`를 다시 호출하여 문서 목록을 갱신.

### 2. 저장 상태 표시 UX
- 파일: `frontend/src/App.jsx`
- 변경 사항:
  - 에디터 제목 옆에 저장 상태 텍스트 추가:
    ```jsx
    <div className="flex items-center justify-between mb-3">
      <h1 className="text-xl font-semibold">에디터</h1>
      <span className="text-xs text-gray-500">
        {isSaving ? '저장 중...' : lastSnapshotTime ? '저장됨' : ''}
      </span>
    </div>
    ```
  - 텍스트 입력 직후에는 잠깐 `저장 중...`이 표시되고,
    자동 저장이 끝난 뒤에는 `저장됨`으로 상태가 바뀜.
- 효과:
  - 사용자가 문서를 편집했을 때 “어디까지 저장됐는지”를 직관적으로 파악할 수 있고,
  - Sidebar에도 자동으로 최신 문서 목록이 반영되어 저장 여부를 확인하기 쉬워짐.

---

## 2025-11-18 – Frontend UX: Create document + immediate Sidebar refresh

### 1. 새 글 생성 시 백엔드 문서 생성 연동
- 파일: `frontend/src/App.jsx`
- 변경 사항:
  - `handleNewDraft`를 async 함수로 변경.
  - 로직:
    - `api.post('/documents', { user_id: user.id })` 호출로 서버에 새 문서 생성 요청.
    - 응답의 `doc_id`를 현재 `docId`로 설정하고,
      - `text`는 빈 문자열,
      - selection/context/recommend 관련 상태는 초기화.
    - 실패 시에는 기존처럼 로컬에서만 `uuidv4()`로 docId를 생성해 fallback 처리.
  - 새 문서 생성 직후:
    - `setLastSnapshotTime(null)`로 저장 상태 초기화.
    - `setRefreshTrigger((v) => v + 1)` 호출로 Sidebar가 즉시 목록을 다시 불러오도록 트리거.

### 2. Sidebar 문서 목록 표시/하이라이팅 개선
- 파일: `frontend/src/Sidebar.jsx`
- 변경 사항:
  - props에 `selectedDocId` 추가:
    - 현재 선택된 문서의 `doc_id`를 받아 목록에서 하이라이팅에 사용.
  - 목록 렌더링:
    - 라벨 결정:
      - `label = (doc.preview_text && doc.preview_text.trim()) || '새 문서'`
      - preview가 비어 있으면 `"새 문서"`를 기본값으로 표시.
    - 선택된 문서 하이라이트:
      - `isActive = selectedDocId === doc.doc_id`
      - 활성 항목에 `bg-purple-50` 같은 배경색 클래스를 적용.
  - `App.jsx`에서 Sidebar 사용 시:
    - `selectedDocId={docId}`를 넘겨 현재 열려 있는 문서와 목록의 선택 상태를 동기화.

---

## 2025-11-18 – Infra: Refactored init scripts & Added Auto-init entrypoint

### 1. Qdrant 초기화 스크립트 구조 개편
- 파일 이동:
  - `api/init_qdrant.py` → `scripts/init_qdrant.py`
- 변경 사항:
  - 컨테이너 경로 기준으로 앱 모듈을 import할 수 있도록 상단에
    ```python
    import os
    import sys

    sys.path.append("/app")
    ```
    추가.
  - CSV 경로를 명시적으로 `/app/train_data.csv`로 고정:
    - `csv_path = "/app/train_data.csv"`
    - Dockerfile에서 해당 위치로 CSV를 복사하도록 맞춤.

### 2. API Dockerfile에서 스크립트/데이터 복사 및 EntryPoint 구성
- 파일: `api/Dockerfile`
- 변경 사항:
  - 빌드 컨텍스트를 루트(`.`)로 사용하기 위해 경로 조정:
    - `COPY api/requirements.txt .`
    - `COPY api/app ./app`
  - init 스크립트/데이터 파일 복사:
    - `COPY scripts /app/scripts`
    - `COPY api/train_data.csv /app/train_data.csv`
  - 엔트리포인트 스크립트 실행을 위한 설정:
    - `RUN chmod +x /app/scripts/entrypoint.sh`
    - `ENTRYPOINT ["/bin/bash", "/app/scripts/entrypoint.sh"]`

### 3. EntryPoint 스크립트 추가
- 파일: `scripts/entrypoint.sh`
- 내용 요약:
  ```bash
  #!/bin/bash
  set -e

  echo "Starting initialization..."
  python /app/scripts/init_qdrant.py || echo "Init skipped or failed"

  echo "Starting Server..."
  exec uvicorn app.main:app --host 0.0.0.0 --port 8000
  ```
- 효과:
  - 컨테이너가 시작될 때마다 Qdrant 컬렉션 및 초기 데이터가 자동으로 준비되며,
    초기화에 실패해도 API 서버는 정상적으로 뜨도록 구성.

### 4. docker-compose에서 API 빌드 설정 변경
- 파일: `docker-compose.mini.yml`
- 변경 사항:
  - `api` 서비스의 `build` 설정을 다음과 같이 수정:
    ```yaml
    api:
      build:
        context: .
        dockerfile: api/Dockerfile
    ```
  - 이렇게 함으로써 루트 컨텍스트 기준으로 `api/`와 `scripts/`를 모두 Docker 빌드에 포함시킬 수 있게 됨.


---

## 2025-11-18 – Phase 1.5: Document Snapshot & Management Pipeline

### 1. Frontend – editor_document_snapshot Throttling 및 상태 관리
- 파일: (에디터/스냅샷 관련) `frontend/src/App.jsx` 및 관련 유틸
- 주요 로직:
  - 사용자가 에디터에 입력할 때마다 바로 스냅샷을 쏘지 않고,
    - **Debounce 2초**: 입력이 멈춘 뒤 2초가 지난 시점,
    - **Throttle 30초**: 최소 30초 간격으로만 전송,
    를 만족하는 경우에만 `editor_document_snapshot` 이벤트를 발생.
  - `lastSnapshotText` 상태를 두어,
    - 현재 텍스트와 이전에 보낸 스냅샷 텍스트가 동일할 경우에는 이벤트를 보내지 않도록 방어.

### 2. Backend – K 이벤트 Consumer (editor_document_snapshot → full_document_store)
- 파일: `api/app/consumer.py`
- 추가 함수: `process_k_events()`
- 동작:
  - Kafka 토픽 `editor_document_snapshot` 구독.
  - 메시지에서 `doc_id`, `full_text`(현재 문서 전체 텍스트), `user_id` 등을 읽어 MongoDB `full_document_store`에 반영.
  - **Case A – 기존 문서가 존재할 때 (Update)**:
    - `prev_text = existing.latest_full_text`
    - `curr_text = payload.full_text`
    - Diff Stub 계산:
      - `len_diff = abs(len(curr_text) - len(prev_text))`
      - `diff_ratio = len_diff / max(len(prev_text), 1)`
    - `update_one`으로 아래 필드 갱신:
      - `previous_full_text = prev_text`
      - `latest_full_text = curr_text`
      - `diff_ratio`
      - `last_synced_at` (현재 UTC ISO)
  - **Case B – 문서가 없을 때 (Insert)**:
    - `insert_one`으로 새 도큐먼트 생성:
      - `doc_id`, `user_id`(있을 경우), `latest_full_text = curr_text`
      - `previous_full_text = None`
      - `diff_ratio = 1.0`
      - `created_at`, `last_synced_at` (현재 UTC ISO)

### 3. Backend – 문서 관리용 API (`GET /documents`, `DELETE /documents/{doc_id}`)
- 파일: `api/app/main.py`
- `GET /documents`:
  - 쿼리 파라미터 `user_id`를 받아, MongoDB `sentencify.full_document_store`에서 해당 유저 문서 목록 조회.
  - `last_synced_at` 내림차순으로 정렬.
  - 응답 항목:
    - `doc_id`
    - `latest_full_text` (에디터 복원용)
    - `preview_text` (latest_full_text 앞 50자)
    - `last_synced_at` (ISO 문자열)
- `DELETE /documents/{doc_id}`:
  - 쿼리 파라미터 `user_id`와 path `doc_id`를 조건으로 `delete_one`.
  - 응답: `{ "deleted": <삭제된 문서 개수> }`

### 4. Frontend – Sidebar와 문서 API 연동
- 파일: `frontend/src/Sidebar.jsx`, `frontend/src/App.jsx`
- Sidebar:
  - `userId`를 prop으로 받아 마운트 시 `GET /documents?user_id=...` 호출.
  - 응답 받은 문서 리스트를 실제 목록으로 렌더링:
    - `preview_text`를 제목처럼 표시.
    - 각 항목 우측에 "삭제" 버튼 추가 → `DELETE /documents/{doc_id}?user_id=...` 호출 후 목록 갱신.
    - 항목 클릭 시 `onSelectDoc({ doc_id, text: latest_full_text })`로 상위(App)에 전달.
- App:
  - `handleSelectDocument(doc)` 핸들러 추가:
    - `doc.doc_id`를 현재 `docId`로 설정.
    - `doc.text`를 에디터의 `text`로 반영.
    - 선택/컨텍스트/추천 상태를 초기화하여 새 문서로 전환.
  - `Sidebar`를 `userId`와 `onSelectDoc`을 넘겨 사용하는 형태로 변경.

---

## 2025-11-19 – Phase 1.5 Step1 (Redis Schema F) 진행 중

### 1. Phase 1.5 착수
- Phase 1.5 Macro Context 단계 시작을 선언하고 Step 1 상태를 **In Progress**로 기록.
- `docker-compose.mini.yml`에 `redis` 서비스 존재 여부, `api/requirements.txt`에 `redis` 패키지 포함 여부를 검증(변경 사항 없음).

### 2. Schema F & Redis 클라이언트
- 파일: `api/app/schemas/macro.py`, `api/app/redis/client.py`, `api/app/redis/__init__.py`, `api/app/schemas/__init__.py`
  - Schema F(`DocumentContextCache`) 정의: `doc_id`, `macro_topic`, `macro_category_hint`, `cache_hit_count`, `last_updated`, `valid_until`, `invalidated_by_diff`, `diff_ratio`.
  - Redis Async 클라이언트(`redis.asyncio`) 추가: `get_redis_client()`, `set_macro_context()`, `get_macro_context()` 구현 및 공용 키 프리픽스 적용.

### 3. Standalone 테스트 & Phase1.5 테스트 리스트
- 파일: `scripts/test_step1_redis.py`
  - 루트 경로에서 실행 가능한 독립 검증 스크립트. 로컬 Redis 접속 → Schema F Dummy 작성 → 저장 후 재로딩 검증.
- 파일: `docs/phase1.5_test_lists.md`
  - Phase 1.5 테스트 항목 시작 (`Redis Connection Test`, `Schema F Validation`).

---

## 2025-11-19 – Phase 1.5 Step1 (Redis Schema F) 완료

### 1. Step 1. Redis Infrastructure & Schema F ✅
- Phase 1.5 Step 1을 완료하고, `docker-compose.mini.yml`의 `redis` 서비스/`api/requirements.txt`의 `redis` 패키지 존재를 재확인(추가 변경 없음).
- Schema F(`DocumentContextCache`, `api/app/schemas/macro.py`)를 v2.3 필드( `macro_llm_version`, `schema_version` 등)로 정의.
- Async Redis 클라이언트(`api/app/redis/client.py`): `get_redis_client()`, `set_macro_context()`, `get_macro_context()` 구현. 기본 호스트 `redis`, TTL 기본 3600초.

### 2. Standalone 테스트 & Phase1.5 테스트 리스트
- 파일: `scripts/test_step1_redis.py`
  - `REDIS_HOST`/`REDIS_PORT` 환경변수로 접속 대상 지정 → Schema F 저장/조회 라운드트립 검증 후 "✅ Step 1 Redis Test Passed" 출력.
- 파일: `docs/phase1.5_test_lists.md`
  - 체크리스트 `Step 1: Redis Connection & Schema F Serialization` 완료 표시.

---

## 2025-11-22 – Phase 1.5 Step4 (Adaptive Scoring) 완료 & Integration 진행 중

### 0. Step 2. Diff Ratio Calculation Logic ✅
- Schema K(`FullDocumentStore`, `api/app/schemas/document.py`) 정의: `blocks`, `latest_full_text`, `previous_full_text`, `diff_ratio`, `last_synced_at`, `schema_version` 등 v2.3 필드 정리.
- Diff 계산 유틸(`api/app/utils/diff.py`) 추가: `calculate_diff_ratio(prev, curr)`가 Levenshtein 거리를 `max(len(prev), 1)`로 정규화하여 0~1 범위 비율을 반환.
- 의존성: `api/requirements.txt`에 `python-Levenshtein` 추가 및 Standalone 테스트(`scripts/test_step2_diff.py`)로 "✅ Step 2 Diff Logic Passed" 확인.

### 1. Step 3. Macro ETL Service ✅
- 파일: `api/app/services/macro_service.py`
  - `.env` 로딩 및 `gemini-2.5-flash` 모델 호출 → LLM 응답 JSON을 정제/파싱하여 `DocumentContextCache`로 직렬화 후 Redis TTL 1시간으로 저장.
- 파일: `scripts/test_step3_macro_llm.py`
  - `AsyncMock`으로 LLM 응답을 패치하고 실제 Redis(`localhost:6379`)에 쓰기/읽기 검증. 성공 시 "✅ Step 3 Macro ETL Service Passed".

### 2. Step 4. Adaptive Scoring Logic ✅
- 파일: `api/app/utils/scoring.py`
  - `calculate_maturity_score()`로 문서 길이를 [0,1] 스케일링, `calculate_alpha()`로 도큐먼트 가중치 계산.
- 파일: `api/app/main.py`
  - `/recommend` 응답 및 A/I 이벤트에 `P_doc`, `doc_maturity_score`, `applied_weight_doc` 필드를 추가하고 `(1-α)·P_vec + α·P_doc` 가중 합 적용.
- 파일: `scripts/test_step4_scoring.py`
  - 짧은/긴 텍스트 케이스와 스코어 블렌딩을 검증하여 "✅ Step 4 Scoring Logic Passed" 출력.

### 3. Integration Wiring & Testing (In Progress)
- 파일: `api/app/main.py`
  - `update_document` 엔드포인트에 `BackgroundTasks`를 도입하고 diff_ratio ≥ 0.10 시 `analyze_and_cache_macro_context()`를 비동기 호출하여 Macro ETL 파이프 연결.
- 파일: `scripts/phase1.5_test_integration.py`
  - 실제 API(`http://localhost:8000`)를 클라이언트로 호출하여 문서 생성 → 짧은 추천 → 긴 텍스트 패치로 diff 발생 → 대기 → 재추천을 통해 `P_doc`/`applied_weight_doc` 변화까지 검증하는 통합 시나리오 스크립트 작성.
- 파일: `docs/phase1.5_test_lists.md`
  - Step 4 테스트 완료 체크 및 "Integration: Full Cycle" 체크리스트를 추가.

---

## 2025-11-24 – Phase 2 Step5 (Analytics Dashboard) 진행 중

### 1. Step 4. Vector DB Migration ✅
- `api/app/services/vector_migration.py`에서 Schema H → Qdrant 업서트 파이프라인 완성, "real_user" payload 태그로 구분.
- Standalone 테스트(`scripts/phase2_test_step4_migration.py`)로 컬렉션/필드 매핑 검증 → "✅ Phase 2 Step 4 Vector Migration Test Passed".

### 2. Step 5. Streamlit Dashboard (In Progress)
- `dashboard/` 모듈 신규 추가:
  - `app.py` + `pages/` 구성으로 Phase 1/1.5/2 뷰 분리.
  - `queries.py`에서 Mongo/Redis 연결, `@st.cache_data` 기반 KPI 질의(`get_total_traffic`, `get_macro_stats`, `get_golden_data_count` 등).
  - `requirements.txt`, `Dockerfile` 작성 후 docker-compose에 `dashboard` 서비스 추가.
- Streamlit 레이아웃:
  - 메인 페이지: KPI, 카테고리 분포, Macro Gatekeeper 지표.
  - Phase별 페이지: Plotly 차트와 Metric 컴포넌트 활용.
- 백엔드 LLM 공급자를 Gemini 2.5 Flash → OpenAI `gpt-4.1-nano`로 이전하여 Macro ETL/Paraphrase 경로 및 테스트를 일괄 수정.
- 문서 업데이트: `docs/phase2_test_lists.md`에 Step5 관련 항목 추가 예정(현 단계에서는 Step4까지 기록됨).

---

## 2025-11-24 – Phase 2 Step 2 ETL Service: Implemented & Verified

### 1. ETL Service Implementation (`api/app/services/etl_service.py`)
- 로그(A, B, C)와 기업 데이터(D)를 `recommend_session_id` 기준으로 Join하는 Aggregation Pipeline을 개선했습니다.
- `was_accepted: true`인 C로그만 학습 데이터로 사용하도록 필터링하고, `A.insert_id`와 `B/C.source_recommend_event_id`를 비교하는 일관성 검사 로직을 추가하여 데이터 정합성을 강화했습니다.

### 2. Integration Test (`scripts/phase2_test_step2_etl.py`)
- 기존 Mock 테스트를 실제 MongoDB에 연결하여 테스트하는 통합 테스트로 재작성했습니다.
- 테스트 시나리오: Mock A/B/C/D 로그를 DB에 주입 → ETL 파이프라인 실행 → 최종 생성된 `training_examples`(Schema H) 데이터의 필드 값과 일관성을 검증합니다.
- 테스트는 Docker 컨테이너 환경에서 실행해야 정상적으로 DB에 연결됩니다. (`docker-compose exec api python ...`)

---

## 2025-11-24 – Phase 2 Step 3 User Profile: Implemented & Verified

### 1. User Profile Service (`api/app/services/profile_service.py`)
- Schema G (`UserProfile`) 기반 프로필 생성 서비스 구현.
- `training_examples`를 집계하여 `user_id` 단위로 프로필을 갱신.
- 주요 지표 계산 로직:
  - **Accept Rate**: 채택된 추천 / 전체 추천 횟수.
  - **Embedding V1**: 채택된 기록의 `context_embedding` 평균(Mean Pooling) 계산. (Phase 3 Personalization 대비)
  - **Preference Vectors**: `preferred_category_vector`, `preferred_strength_vector` (Tone) 분포 계산.
- Schema Update: `user_embedding_v1` 필드(List[float])를 `UserProfile` 스키마에 추가.

### 2. Service Verification (`scripts/phase2_test_step3_profile.py`)
- Docker 컨테이너 내부 통합 테스트 스크립트 작성.
- 검증 시나리오:
  - 가상의 유저 로그 및 Training Examples (수락 3, 거절 2) 주입.
  - `ProfileService.update_user_profile` 실행.
  - 결과 검증: `recommend_accept_rate` (0.6), 임베딩 평균값, 카테고리 분포 벡터의 정확성 확인.
- 결과: "✅ Phase 2 Step 3 User Profile Service Test Passed"

## 2025-11-24 – Phase 2 Step 5 Dashboard Gap Analysis
- **Analysis**: Compared `dashboard_spec.md` with current implementation.
- **Findings**:
    - **Missing Pages**: Phase 3 (User Insights), Phase 4 (Automation) pages are not created.
    - **Query Gap**: Missing queries for Correction Funnel (Phase 2), Clustering/Embeddings (Phase 3), and Automation metrics (Phase 4).
    - **Bug Found**: `get_user_profile_coverage` queries wrong collection `user_profile`; should be `users`.
    - **Component Gap**: `dashboard/components/` directory missing; charts are not modularized.
- **Next**: Fix query bug, implement missing queries, and add Phase 3/4 pages.
- **Fix**: Phase 2 Dashboard Fix: Fixed collection name bug & Added Correction Funnel Chart.

---

## 2025-11-24 – Phase 2 Step 5 Dashboard Queries: Implemented, Fixed & Verified

### 1. Dashboard Query Implementation & Bug Fix (`dashboard/queries.py`)
- **`get_correction_funnel_data`**: The initial stub function was replaced with a robust MongoDB aggregation pipeline. The new pipeline correctly calculates the A/B/C funnel by grouping unique `recommend_session_id`s from `log_a_recommend` first, then using `$lookup` to count corresponding `log_b_run` and `log_c_select` events. This fixes a bug where `views_a` were overcounted. The function now also accepts an optional `user_id` for filtered queries.
- **`get_user_profile_coverage`**: Fixed a bug where the function was not correctly calculating the coverage ratio. It now accepts an optional `user_filter` dictionary to scope the query, allowing for isolated testing. The logic was corrected to divide the count of users with profile embeddings by the total number of (filtered) users.

### 2. Dashboard Integration Test (`scripts/phase2_test_step5_dashboard.py`)
- **Test Creation**: A new integration test script was created following TDD principles to verify the dashboard queries against a live MongoDB instance.
- **Data Isolation**: The test's `setup_test_data` function now injects a precise number of mock A, B, and C logs linked by session IDs for a specific test user (`dashboard_tester`).
- **Query Verification**: The test calls the dashboard query functions (`get_correction_funnel_data` and `get_user_profile_coverage`) using filters to ensure the queries only run on the mock data set. Assertions now confirm that the returned counts (10 views, 5 runs, 2 accepts) and coverage ratio (0.25) are exactly as expected.

### 3. Status
- This work completes the final implementation and verification for the Phase 2 Dashboard's backend analytics, specifically the Correction Funnel and User Coverage metrics. The integration test now passes, confirming the data pipeline from logs to dashboard queries is working correctly.

---

## 2025-11-24 – Dashboard v2.4 Control Tower 구축

### 완료 항목
- [x] 의존성 정리: `dashboard/requirements.txt`에 `streamlit-agraph` 추가.
- [x] 데이터 레이어 재구성: `dashboard/queries/` 패키지 신설 (`mongo.py`, `__init__.py`)로 v2.4 스키마(A~L) 기준 조회/헬스체크/플로우/비용 계산 함수 구현 및 `user_id` 필터 공통 적용.
- [x] UI 컴포넌트 추가: `dashboard/components/`에 `topology_graph.py`(agraph 토폴로지), `inspector.py`(노드별 메트릭), `charts.py`(Sankey/latency 차트) + `__init__.py`.
- [x] 메인 앱 교체: `dashboard/app.py`에서 사이드바 헬스체크(🟢/🔴), `user_id` 필터, 5초 자동 새로고침 토글, A 이벤트 라이브 티커 구현.
- [x] 페이지 교체: `dashboard/pages/0_System_Map.py`, `1_Data_Flow.py`, `2_User_Insights.py`, `3_Auto_Gen_ROI.py` 신설(Phase 2~4 데이터 없을 시 try/except로 mock/“Data pending” 처리). 기존 Phase1.x 페이지 삭제.

### 비고
- Redis/Vector 헬스체크는 env 기반 TCP/INFO 조회, 데이터 미존재 시 0/False로 폴백.
- LLMOps 비용은 `B` 카운트 × 고정 단가(0.002) 단순 계산. Macro 큐는 `K.diff_ratio>=0.1`.
- 토폴로지 활성화 조건은 최근 10초 이내 이벤트 존재 여부로 산정.

---

## 2025-11-24 – Topology 고정 & 트래픽 시뮬레이터 추가

### 완료 항목
- [x] 토폴로지 정적 레이아웃: `dashboard/components/topology_graph.py`에서 physics 비활성화, x/y 좌표 하드코딩(0~800, 0~600)으로 노드 고정.
- [x] Inspector 지속성: `dashboard/pages/0_System_Map.py`에서 선택 노드를 `st.session_state['selected_node']`에 보존해 새로고침에도 유지.
- [x] 실시간 시뮬레이터: `scripts/simulate_traffic.py` 추가. 2s 주기 A, 5s B, 10s C, 30s K(diff=0.15) 이벤트 생성하며 랜덤 latency_ms로 대시보드 변동 확인 가능. 콘솔 로그 출력 포함.

### 비고
- 시뮬레이터는 `MONGO_URI`/`MONGO_DB_NAME`, `REDIS_HOST`/`REDIS_PORT` 환경변수 사용, 기본은 localhost.
- B 이벤트 수가 비용 계산 근거이며, K(diff>=0.1) 갱신으로 Macro 큐 길이 변화 테스트 가능.

---

## 2025-11-24 – Dashboard Connectivity & Simulator 확장

### 완료 항목
- [x] 시뮬레이터 확장: `scripts/simulate_traffic.py`가 A/B/C/K 외에 E(context_block), I(recommend_log), F(document_context_cache)까지 생성해 토폴로지 모든 노드(Emb Model, VectorDB, Redis, GenAI Macro)가 점등됨.
- [x] Inspector 보강: `dashboard/components/inspector.py`에 Mongo/VectorDB/Worker/Emb Model 핸들러 추가. Mongo는 최근 A 3건 JSON 표시, VectorDB는 E 카운트와 Index Ready 메시지, Worker는 diff>=0.1 K 카운트, Emb Model은 I 기반 지연 시간 사용.
- [x] VectorDB 헬스 폴백: `dashboard/queries/mongo.py`에서 TCP 실패 시 최근 1분 이내 E 문서 존재 여부로 “시뮬레이터 온라인” 판정.

### 비고
- F 생성은 K 갱신 후 2초 지연 삽입으로 Redis/GenAI Macro 활성 상태를 확인.
- 시뮬레이터 루프 주기 1초, 이벤트 주기 A(2s)/B(5s)/C(10s)/K(30s).

---

## 2025-11-24 – 시각화 동적 강화 (Heatmap & Burst Flow)

### 완료 항목
- [x] 노드 열지도: `dashboard/queries/mongo.py`의 `get_node_recency_map`이 각 컴포넌트의 최근 이벤트로부터 경과 초를 반환(미존재 시 999). `topology_graph.py`가 이 값을 바탕으로 3/7/15초 구간 네온→웜→쿨→아이들 색상 적용.
- [x] 엣지 애니메이션: `topology_graph.py` Config에 dashed curved 링크 설정으로 흐름감을 부여.
- [x] 시스템 맵 연동: `pages/0_System_Map.py`가 새 recency 맵을 사용해 그래프/Inspector를 유지.
- [x] 버스트 트래픽: `scripts/simulate_traffic.py`가 Burst 모드(A→0.5s→B→0.5s→C→2s→F, 매번 K 포함) 후 4~6초 휴지로 핫/쿨 전이를 명확히 표현.

### 비고
- 버스트마다 Macro diff=0.15를 트리거하고 2초 후 F를 삽입해 Redis/GenAI Macro 노드가 주기적으로 점등.
- VectorDB 헬스는 실TCP 실패 시에도 최근 E 삽입으로 “green” 처리되어 데모 환경에서 끊김 없이 표시.
---

## 2025-11-24 – QA: Dashboard v2.4 Queries Integration Test

### 1. Test Suite Implementation (`scripts/dashboard/test/test_dashboard_queries.py`)
- **TDD Principle**: Following the Test-Driven Development principle, a new Pytest suite was created to validate the dashboard's backend queries.
- **Mocking Environment**: The test utilizes `mongomock` and `fakeredis` to create an isolated, in-memory database environment, ensuring tests are fast, repeatable, and independent of external DB state.
- **Seeding Logic**: A pytest fixture (`mock_db`) was implemented to seed the mock database with a precise scenario, including data for multiple users (`test_user`, `other_user`) to verify user-level filtering.

### 2. Query Verification and Bug Fixes
- **Test Coverage**: The suite validates the following key queries from `dashboard/queries/mongo.py`:
  - `check_mongo_health()`, `check_redis_health()`
  - `get_activity_window_map()`
  - `get_flow_counts()`, `get_sankey_links()`
  - `get_cost_estimate()`
- **Bug Fix & Verification**:
  - The integration test successfully identified and led to the fix of a data isolation bug in `get_correction_funnel_data` and `get_user_profile_coverage`.
  - By adding optional filters to the query functions and applying them in the test, the queries now return accurate, isolated results.
- **Status**: ✅ All tests in `test_dashboard_queries.py` now pass, confirming that the dashboard's data aggregation logic is correct and robust.

---

## 2025-11-24 – Dashboard Visualization Upgrade & ELK Integration Start

### 1. Dashboard Upgrade (Live Stream & Topology)
- **Live Activity Stream (`dashboard/app.py`)**:
  - 메인 페이지를 "실시간 활동 스트림"으로 개편.
  - A(추천)/B(실행)/C(선택) 로그를 통합하여 시간순으로 표시하는 `get_recent_activity_stream` 쿼리 구현 및 적용.
- **Topology Map Refactoring (`dashboard/components/topology_graph.py`)**:
  - `streamlit-agraph` 설정을 `hierarchical=True`, `direction='LR'`(Left-to-Right)로 변경하여 깔끔한 파이프라인 구조 시각화.
  - 노드 아이콘 적용 및 `_heat_color` 로직을 통해 데이터 흐름에 따른 실시간 색상 변화(Heatmap) 구현.
  - `scripts/simulate_traffic.py`의 Burst 트래픽으로 시각화 효과 검증 완료.

### 2. ELK Stack Integration (Phase 2.5 착수)
- **Roadmap & Architecture**:
  - `docs/phase2.5/elk_로드맵.md` 작성: Streamlit 폐기 및 ELK 전면 전환 전략 수립.
  - `docs/아키텍쳐2-4.md` 업데이트: Kafka Consumer Group을 활용한 **병렬 로그 구독(Parallel Subscription)** 아키텍처 명시 (MongoDB: 보존/ETL, ELK: 관제/BI).
- **Infrastructure Setup**:
  - `docker-compose.elk.yml` 생성: Elasticsearch, Logstash, Kibana 컨테이너 정의 (메모리 최적화 포함).
  - `elk/logstash/config/logstash.yml`, `elk/kibana/config/kibana.yml` 기본 설정 파일 생성.
  - **Logstash Pipeline (`elk/logstash/pipeline/logstash.conf`)**:
    - Kafka Input 플러그인 설정: `editor_recommend_options`, `editor_run_paraphrasing` 등 주요 토픽 구독.
    - `filter` 단계에서 `json { source => "message" }`로 파싱 처리 (CRLF 및 JSON 에러 해결).
    - Elasticsearch Output 설정: `sentencify-logs-*` 인덱스로 실시간 적재 파이프라인 구축.
- **Verification**:
  - **Unit Test (`scripts/test_elk_connection.py`)**:
    - Elasticsearch 연결 및 Logstash 파이프라인(Kafka -> ES) 정상 작동 확인 ✅
  - **Integration Test (`scripts/phase2.5_test_elk_pipeline.py`)**:
    - API 호출부터 Elasticsearch 적재까지의 E2E 파이프라인 정상 작동 확인 ✅

### 3. Golden Data Mocking (For ELK Pipeline 2)
- **Objective:** ELK의 Golden Data 시각화 파이프라인을 테스트하기 위해, ETL을 거치지 않고 MongoDB에 강제로 학습 데이터(`training_examples`)를 주입.
- **Action**:
  - `scripts/inject_mock_golden_data.py` 작성 및 실행.
  - MongoDB에 `training_examples` 컬렉션 생성 및 Mock 데이터 5건 적재 완료.
  - 이를 통해 후속 작업인 "MongoDB -> ES 동기화 스크립트" 개발 준비 완료.

### 4. Golden Data Sync Pipeline (MongoDB -> Elasticsearch)
- **Script (`scripts/sync_golden_to_es.py`)**:
  - **Incremental Sync:** Elasticsearch에서 가장 최근 `created_at` 체크포인트를 조회하여, 그 이후 생성된 MongoDB 데이터만 가져오는 효율적인 로직 구현.
  - **Bulk Upsert:** `helpers.bulk`를 사용하여 대량 데이터를 ES 인덱스(`sentencify-golden-YYYY.MM`)에 고속 적재.
  - **Verification:** Mock Data 5건이 성공적으로 ES로 동기화됨을 확인 (`[Synced 5 documents]`).
- **Dependency Update**:
  - `api/requirements.txt`에 `elasticsearch<9.0.0` 및 `python-dateutil` 추가 (ES 8.x 서버 호환성 확보).

---

## 2025-11-25 – Strategic Pivot: ELK Removed & Dashboard Control Tower

### 1. Strategic Change
- **Deprioritized ELK Stack**: Suspended Phase 2.5 ELK integration to reduce infrastructure complexity.
- **Dashboard as Control Tower**: Confirmed `Streamlit Dashboard` as the primary monitoring tool (polling MongoDB directly).
- **Single Path Architecture**:
  - Removed "Dual Subscription".
  - Validated "Kafka -> Consumer -> MongoDB" as the Single Source of Truth (SSOT).

### 2. Documentation Update
- **Architecture v2.4**:
  - Updated `docs/아키텍쳐2-4.md` to reflect the removal of ELK and the elevation of Streamlit Dashboard.
  - Clarified the data flow: API -> Kafka -> Mongo -> Dashboard/ETL.

---

## 2025-11-26 – Dashboard Enhancements: Detailed Inspector & Logs

### 1. Dashboard Query 확장 (`dashboard/queries/mongo.py`)
- **Generic Log Fetcher**: `get_recent_docs(collection_name, limit)` 함수를 추가하여, 특정 MongoDB 컬렉션의 최신 로그를 표준화된 방식으로 조회 가능하게 함.
- **VectorDB Metrics**: `get_recent_upserts` 함수를 추가하여, VectorDB에 업서트된 최신 Context Block(COLL_E)을 조회하는 로직 구현.

### 2. Inspector 컴포넌트 고도화 (`dashboard/components/inspector.py`)
- **Node-specific Inspectors**: 기존에 미구현된 노드(`Emb Model`, `VectorDB`, `GenAI (Run/Macro)`)에 대한 전용 Inspector 뷰를 구현.
- **Unified Log View**: 모든 노드 Inspector 하단에 `_render_recent_logs` 공통 헬퍼를 사용하여 관련 최근 로그/이벤트를 표시하도록 개선.
  - **VectorDB**: 총 Context Block 수 및 최근 Upsert 로그.
  - **Redis**: Micro(LLM Response) vs Macro(Context) 캐시 분포 차트 및 각 타입별 최신 키 샘플(Logs).
  - **API**: 최근 시스템 로그 및 Anomaly(>2000ms Latency) 로그.
  - **Worker/GenAI**: 관련 작업 큐 및 실행 로그(COLL_B, COLL_F) 표시.
- **Effect**: 사용자가 System Map의 노드를 클릭하면, 해당 컴포넌트의 핵심 메트릭(캐시 적중률, 업서트 수 등)과 실제 최근 동작 로그를 즉시 확인할 수 있어 "Control Tower"로서의 가시성이 대폭 향상됨.

---

## 2025-11-26 – System Enhancements & Dashboard Fixes

### 1. ETL Worker 주기 변경 및 Qdrant 데이터 형식 정제
- **ETL Worker 주기 조정**: `api/app/etl_worker.py`의 `sync_vectors` 실행 주기를 `ETL_INTERVAL_SECONDS` 환경변수를 통해 설정 가능하도록 변경 (기본값 24시간).
- **Qdrant 데이터 형식 일치**: `/recommend` API (`api/app/main.py`)에서 `context_block` 이벤트 (`e_event`)를 생성할 때 `field` 값을 포함하도록 수정. `etl_worker.py`도 Qdrant에 업서트하는 Payload에 `content` (full text)와 `field`를 포함하도록 변경하여 Qdrant의 `PointStruct` 형식과 일관성을 유지.

### 2. Macro Cache 대시보드 조회 문제 해결
- **Macro Service 동기화**: `api/app/services/macro_service.py`가 LLM을 통한 Macro 분석 완료 후, Redis 캐시뿐만 아니라 MongoDB의 `document_context_cache` (COLL_F) 컬렉션에도 결과를 동기화하도록 수정. 이로써 대시보드가 MongoDB에서 Macro 업데이트 내역을 조회할 수 있게 됨.
- **Redis Inspector 패턴 수정**: 대시보드의 `dashboard/queries/redis.py` 및 `dashboard/components/inspector.py`에서 Macro Redis 캐시를 조회하는 패턴을 실제 API가 사용하는 `macro_context:*` 패턴으로 일치시킴. Micro/Macro 캐시 조회를 다시 탭으로 분리하고, 각 탭 내에서 최신순(Idle Time)으로 정렬하여 표시하도록 개선.

### 3. Data Flow Live Monitor 페이지 수정
- **컬렉션 이름 일치**: `dashboard/pages/4_Data_Flow_Live.py` 페이지에서 실시간 트래픽을 모니터링할 때 사용하던 MongoDB 컬렉션 이름(`log_a`, `log_b`, `log_c`)을 최신 v2.4 스키마(`COLL_A`, `COLL_B`, `COLL_C` 상수로 참조)에 맞게 수정. 페이지가 현재 시스템의 데이터를 정확히 반영할 수 있도록 개선.

### 4. VectorDB 업서트 품질 게이트 (`etl_worker.py`)
- **수락된 Context만 업서트**: `etl_worker.py`의 `sync_vectors` 로직을 수정하여, `context_block` (E)가 Qdrant에 업서트될 때 반드시 `editor_selected_paraphrasing` (C) 로그에서 `was_accepted: True`인 경우가 확인될 때만 처리하도록 Quality Gate를 구현.
- **건너뛰기 로직**: C 로그가 없거나 `was_accepted: False`인 경우, 해당 E 로그는 Qdrant에 업서트하지 않고 즉시 `vector_synced: True`로 마킹하여 재처리를 방지하고 건너뛰도록 로직을 단순화.
- **ETL 주기 변경**: 테스트 용이성을 위해 `ETL_INTERVAL_SECONDS`를 5초로 일시 변경.

### 5. 대시보드 토폴로지 수정 (`dashboard/components/topology_graph.py`)
- **정확한 ETL 흐름 반영**: `API -> Emb Model -> VectorDB` 엣지를 제거하고, `Mongo -> Worker -> Emb Model -> VectorDB` 흐름을 반영하도록 시스템 맵의 엣지를 수정.

### 6. User Embedding EDA 스크립트 추가 (`scripts/phase3/step1_eda.py`)
- **`correction_history` 기반 유저 임베딩 추출**: `scripts/phase3/step1_eda.py` 스크립트를 작성하여 `correction_history` 컬렉션에서 `selected_index`가 있는 최종 문장만 추출, 임베딩 모델(`klue/bert-base`)을 통과시켜 유저별 평균 임베딩 벡터를 계산하고 결과를 출력. User ID 추출 로직(`$oid` 처리 포함) 및 임베딩 서비스 임포트 경로 오류 수정 후 실행 성공 확인.

### 8. Recommendation Cycle 완성 (Sync & Serving)

- **User Profile Schema 개선**: `UserProfile` 스키마를 수정하여 `preferred_category_vector` 등을 유연한 Map(`Dict`) 형태로 변경하고, 수락률 지표를 세분화함.
- **Profile Service 리팩토링**: `ProfileService`가 중간 데이터(H)에 의존하지 않고 A/B/C/D 원본 로그를 직접 집계하여 통계와 임베딩을 계산하도록 로직을 완성함.
- **Sync Service 구현**: MongoDB에 저장된 최신 User Profile을 Qdrant(`user_behavior_v1`)로 동기화하는 `SyncService`를 구현함. (BERT 768차원 벡터 사용)
- **ETL Worker 자동화**: `etl_worker.py`의 `process_training_ops`에 `SyncService`를 통합하여, 프로필 갱신 직후 Qdrant 동기화가 자동으로 이루어지도록 연결함.
- **추천 API 연동**: `recommendation_service.py` (유사 유저 기반 강도 추천 로직)를 구현하고, `main.py`의 `/recommend` 엔드포인트에 연결하여 실제 추천에 반영되도록 함.
- **단위 테스트 추가**: `tests/test_recommendation.py`, `tests/test_sync_service.py` 작성 완료.

### 9. Docker 재빌드 및 재시작 필요
- 위 변경 사항들은 `api` 서비스와 `dashboard` 서비스의 코드 변경을 포함하므로, 변경 사항을 적용하기 위해서는 해당 Docker 컨테이너를 재빌드하고 재시작해야 합니다. (예: `docker-compose up --build -d` 또는 `docker-compose restart api dashboard`)