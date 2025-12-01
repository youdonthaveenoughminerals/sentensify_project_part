import hashlib
from datetime import datetime, timezone
from qdrant_client.models import PointStruct
from .client import get_qdrant_client
from app.utils.embedding import get_embedding


def insert_with_spec(
    context_full: str,
    doc_id: str,
    field: str,
    user_id: str = None,
    intensity: str = "moderate",
    source_type: str = "user_input"
):
    """
    Spec 기준 Payload로 Qdrant에 삽입

    Args:
        context_full: 전체 문맥 텍스트 (임베딩 대상)
        doc_id: 문서 ID
        field: 카테고리 (thesis/email/report/article/...)
        user_id: 사용자 ID (optional)
        intensity: weak/moderate/strong
        source_type: user_input/synthetic/real

    Returns:
        context_hash (str): 삽입된 데이터의 고유 해시
    """
    client = get_qdrant_client()

    # 1. context_hash 계산
    context_hash = hashlib.sha256(
        f"{doc_id}:{context_full}".encode('utf-8')
    ).hexdigest()

    # 2. 임베딩 생성
    embedding_vector = get_embedding(context_full)

    # 3. Payload 구성 (Spec 기준)
    payload = {
        "context_hash": context_hash,
        "doc_id": doc_id,
        "user_id": user_id,
        "preview_text": context_full[:100],
        "field": field,
        "intensity": intensity,
        "embedding_version": "v1.0",
        "source_type": source_type,
        "created_at": datetime.now(timezone.utc).isoformat()
    }

    # 4. Qdrant에 저장
    client.upsert(
        collection_name="context_block_v1",
        points=[
            PointStruct(
                id=context_hash,
                vector=embedding_vector,
                payload=payload
            )
        ]
    )

    return context_hash
