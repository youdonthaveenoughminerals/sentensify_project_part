#!/usr/bin/env bash
set -euo pipefail

# docker-compose 파일과 Mongo DB 이름은 환경변수로 오버라이드 가능
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.mini.yml}"
DB_NAME="${MONGO_DB_NAME:-sentencify}"

# 호스트 / 컨테이너 내 데이터 디렉터리
DATA_DIR_HOST="./data/import"
DATA_DIR_IN_CONTAINER="/data/import"

echo "[info] importing company JSON into MongoDB (${DB_NAME})..."
echo "       host data dir: ${DATA_DIR_HOST}"

if [ ! -d "${DATA_DIR_HOST}" ]; then
  echo "[error] ${DATA_DIR_HOST} 디렉터리가 없습니다. JSON 파일을 여기에 넣어주세요." >&2
  exit 1
fi

echo "[info] 현재 호스트 data/import 내용:"
ls "${DATA_DIR_HOST}" || true
echo

########################################
# 1. D 스키마: correction_history
########################################
CORR_FILE_HOST="${DATA_DIR_HOST}/correction_history.json"
CORR_FILE_CONT="${DATA_DIR_IN_CONTAINER}/correction_history.json"

if [ -f "${CORR_FILE_HOST}" ]; then
  echo "[info] importing correction_history.json -> correction_history 컬렉션"
  docker compose -f "${COMPOSE_FILE}" exec mongo \
    mongoimport \
      --db "${DB_NAME}" \
      --collection correction_history \
      --file "${CORR_FILE_CONT}" \
      --jsonArray
  echo "[ok] correction_history import finished."
else
  echo "[warn] ${CORR_FILE_HOST} 파일이 없습니다. correction_history는 건너뜁니다."
fi

########################################
# 2. (선택) usage_summary
########################################
USAGE_FILE_HOST="${DATA_DIR_HOST}/usage_summary.json"
USAGE_FILE_CONT="${DATA_DIR_IN_CONTAINER}/usage_summary.json"

if [ -f "${USAGE_FILE_HOST}" ]; then
  echo "[info] importing usage_summary.json -> usage_summary 컬렉션"
  docker compose -f "${COMPOSE_FILE}" exec mongo \
    mongoimport \
      --db "${DB_NAME}" \
      --collection usage_summary \
      --file "${USAGE_FILE_CONT}" \
      --jsonArray
  echo "[ok] usage_summary import finished."
else
  echo "[info] usage_summary.json 파일이 없으므로 usage_summary는 건너뜁니다."
fi

########################################
# 3. (선택) client_properties
########################################
CLIENT_FILE_HOST="${DATA_DIR_HOST}/client_properties.json"
CLIENT_FILE_CONT="${DATA_DIR_IN_CONTAINER}/client_properties.json"

if [ -f "${CLIENT_FILE_HOST}" ]; then
  echo "[info] importing client_properties.json -> client_properties 컬렉션"
  docker compose -f "${COMPOSE_FILE}" exec mongo \
    mongoimport \
      --db "${DB_NAME}" \
      --collection client_properties \
      --file "${CLIENT_FILE_CONT}"
  echo "[ok] client_properties import finished."
else
  echo "[info] client_properties.json 파일이 없으므로 client_properties는 건너뜁니다."
fi

########################################
# 4. (선택) event_raw
########################################
EVENT_FILE_HOST="${DATA_DIR_HOST}/event_raw.json"
EVENT_FILE_CONT="${DATA_DIR_IN_CONTAINER}/event_raw.json"

if [ -f "${EVENT_FILE_HOST}" ]; then
  echo "[info] importing event_raw.json -> event_raw 컬렉션"
  docker compose -f "${COMPOSE_FILE}" exec mongo \
    mongoimport \
      --db "${DB_NAME}" \
      --collection event_raw \
      --file "${EVENT_FILE_CONT}"
  echo "[ok] event_raw import finished."
else
  echo "[info] event_raw.json 파일이 없으므로 event_raw는 건너뜁니다."
fi

echo "[done] company data import script finished."
