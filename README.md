-----

# Sentencify-MVP (Phase 2.5 인프라 구축 완료)

이 프로젝트는 문맥 기반 문장 교정 추천 시스템 **Sentencify**의 MVP 버전입니다.
현재 **Phase 2.5** 인프라 구축 단계가 완료되었으며, ELK Stack을 도입하여 실시간 관제 및 데이터 분석 파이프라인을 확보했습니다. (대시보드 구성 예정)

##  현재 진행 상황 (Current Progress)

  - [x] **Phase 1 & 1.5: 추천 엔진 완성**
      - `P_rule`, `P_vec`, `P_doc` 하이브리드 추천 로직
      - Redis 기반 매크로 컨텍스트 캐싱
  - [x] **Phase 2: 데이터 파이프라인 완성**
      - Kafka -> MongoDB 실시간 로그 적재
      - ETL 파이프라인: Raw Log -> Golden Data (`training_examples`) 생성
  - [ ] **Phase 2.5: ELK 관제 시스템 (진행 중)**
      - [x] **Real-time Ops:** Kafka -> Logstash -> Elasticsearch (실시간 로그 수집)
      - [x] **Biz Analytics:** MongoDB(H) -> ES 증분 동기화 (비즈니스 지표 분석)
      - [ ] **Dashboard:** Kibana 시각화 및 대시보드 구성 (예정)

-----

##  실행 전 필수 준비 사항 (Prerequisites)

프로젝트를 실행하기 전에 **반드시** 아래 3가지 파일/설정을 준비해야 합니다.
*(필요한 파일은 공유된 구글 드라이브 링크를 참고하세요)*

### 1\. 모델 및 데이터 파일 배치

다운로드 받은 파일들을 아래 경로에 정확히 위치시켜 주세요.

  * **KoBERT 모델 폴더**
      * 소스: `kobert-classifier` 폴더 (내부에 `config.json`, `spiece.model` 등 포함)
      * 타겟 경로: **`./models/kobert-classifier/`**
  * **학습 데이터 (Qdrant 적재용)**
      * 소스: `train_data.csv`
      * 타겟 경로: **`./api/train_data.csv`**

### 2\. 환경 변수 설정 (.env)

프로젝트 루트 디렉토리에 `.env` 파일을 생성하고 아래 내용을 입력하세요.

```bash
# .env 파일 생성
OPENAI_API_KEY=sk-proj-... (본인의 API KEY 입력)
```

-----

##  실행 방법 (How to Run)

Docker Compose를 사용하여 서비스를 실행합니다. 목적에 따라 두 가지 방식이 있습니다.

### Option A: Core 서비스만 실행 (가볍게)
API, DB, Kafka 등 핵심 기능만 실행합니다.
```bash
docker-compose -f docker-compose.mini.yml up -d --build
```

### Option B: Core + ELK 관제 스택 전체 실행 (권장)
Kibana 대시보드까지 포함하여 전체 시스템을 실행합니다. (RAM 8GB 이상 권장)
```bash
docker-compose -f docker-compose.mini.yml -f docker-compose.elk.yml up -d --build
```

-----

## 🔗 접속 정보 (Access Points)

서비스가 정상적으로 실행되면 아래 주소로 접속할 수 있습니다.

| 서비스 | URL | 설명 |
| :--- | :--- | :--- |
| **Frontend** | `http://localhost:5173` | 웹 에디터 및 사용자 인터페이스 |
| **Backend API** | `http://localhost:8000/docs` | Swagger API 명세서 및 테스트 |
| **Kibana** | `http://localhost:5601` | 실시간 로그 및 비즈니스 대시보드 |
| **Streamlit** | `http://localhost:8501` | (Legacy) 관리자용 어드민 툴 |

-----

## 🛠️ 주요 관리 스크립트 (Ops Scripts)

컨테이너 내부에서 다음 스크립트를 실행하여 시스템을 관리할 수 있습니다.

### 1. Golden Data 동기화 (MongoDB -> Elasticsearch)
ETL로 생성된 학습 데이터를 Kibana에서 보려면 동기화가 필요합니다.
```bash
# 1회 실행 (API 컨테이너 내부)
docker-compose -f docker-compose.mini.yml -f docker-compose.elk.yml exec api python scripts/sync_golden_to_es.py
```

### 2. 트래픽 시뮬레이터 (부하 테스트)
대시보드에 실시간 로그가 흐르는 것을 보고 싶을 때 사용합니다.
```bash
docker-compose -f docker-compose.mini.yml -f docker-compose.elk.yml exec api python scripts/simulate_traffic.py
```

### 3. ELK 연결 테스트
ELK 파이프라인이 정상 작동하는지 검증합니다.
```bash
docker-compose -f docker-compose.mini.yml -f docker-compose.elk.yml exec -e API_HOST="http://api:8000" -e ELASTICSEARCH_HOST="http://elasticsearch:9200" -e KAFKA_BOOTSTRAP_SERVERS="kafka:9092" api python scripts/phase2.5_test_elk_pipeline.py
```