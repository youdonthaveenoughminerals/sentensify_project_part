"""
애플리케이션 설정 및 환경 변수 관리
"""
import os
from pathlib import Path

# 로그 디렉토리
LOG_DIR = Path("logs")

# Kafka 설정
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
KAFKA_ENABLED = os.getenv("KAFKA_ENABLED", "true").lower() != "false"

# Gemini API 설정
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

# MongoDB 설정
MONGO_URI = os.getenv("MONGO_URI", "mongodb://mongo:27017")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "sentencify")

# Qdrant 설정
QDRANT_HOST = os.getenv("QDRANT_HOST", "qdrant")
QDRANT_PORT = os.getenv("QDRANT_HOST", "6333")

# Redis 설정
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = os.getenv("REDIS_PORT", "6379")

# API 버전
API_VERSION = "v1"
SCHEMA_VERSION = "phase1_aie_v1"
MODEL_VERSION = "phase1_stub_v1"
EMBEDDING_VERSION = "embed_v1_stub"
