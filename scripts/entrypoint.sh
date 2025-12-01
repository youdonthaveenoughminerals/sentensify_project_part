#!/bin/bash
set -e

# Helper function to wait for Qdrant
wait_for_qdrant() {
    echo "⏳ Waiting for Qdrant to be ready..."
    # 최대 60초 대기
    for i in {1..30}; do
        # python 스크립트로 연결 테스트 (성공 시 0 반환)
        if python -c "import os, sys; from qdrant_client import QdrantClient; client = QdrantClient(host=os.getenv('QDRANT_HOST', 'qdrant'), port=6333); client.get_collections()" > /dev/null 2>&1; then
            echo "✅ Qdrant is ready!"
            return 0
        fi
        sleep 2
        echo "   ... retrying Qdrant connection ($i/30)"
    done
    echo "❌ Qdrant connection failed after 60 seconds."
    return 1
}

# 환경변수 RUN_INIT이 true일 때만 초기화 스크립트 실행
if [ "$RUN_INIT" = "true" ]; then
    echo "🚀 [Init] Starting Data Initialization Sequence..."
    
    # 1. MongoDB Initialization (Drop & Import All)
    echo "📥 [1/3] Running MongoDB Initialization..."
    # init_mongo.py 내부에 MongoDB 접속 대기 로직 포함되어 있음
    python /app/scripts/init_mongo.py || echo "❌ MongoDB Init failed"
    
    # 2. Qdrant Readiness Check (CRITICAL)
    # Qdrant가 뜨기 전에 스크립트를 실행하면 Connection Refused가 발생하므로 여기서 확실히 기다림
    wait_for_qdrant
    
    # 3. Qdrant Data Load
    echo "🧠 [2/3] Running Qdrant Init (Context & Correction)..."
    # init_qdrant.py loads train_data.csv -> context_block_v1 and correction_history.json -> correction_history_v1
    python /app/scripts/init_qdrant.py || echo "❌ Qdrant Context/Correction Init failed"

    # Give Qdrant a moment to breathe after heavy load
    echo "⏳ Pausing for 5s to let Qdrant stabilize..."
    sleep 5

    echo "👤 [3/3] Running Qdrant Init (User Profile)..."
    python /app/scripts/phase3/step3_upload_to_qdrant.py || echo "❌ Qdrant User Profile Init failed"
    
    echo "✅ [Init] All Initialization Steps Completed."
else
    echo "⏩ Skipping Data Initialization (Set RUN_INIT=true to run)"
fi

# 인자가 있으면(예: python -m app.consumer) 그 명령어를 실행
if [ "$#" -gt 0 ]; then
    echo "🚀 Executing command: $@"
    exec "$@"
else
    # 초기화가 끝난 후 API 서버 시작
    echo "🚀 Starting API Server..."
    exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
fi
