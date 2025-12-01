from collections import defaultdict

from .client import get_qdrant_client


# 조회
def search_vector(query_vector, limit=15):
    client = get_qdrant_client()

    return client.query_points(
        collection_name="context_block_v1",
        query=query_vector,
        limit=limit,
    ).points


def compute_p_vec(query_vector, limit=15):
    try:
        print(
            f"[DEBUG] 2. Query Vector Generated: dim={len(query_vector)}, "
            f"sample={query_vector[:5]}...",
            flush=True,
        )
    except Exception:
        print("[DEBUG] 2. Query Vector Generated: <unprintable>", flush=True)

    results = search_vector(query_vector, limit)
    category_scores = defaultdict(float)

    for hit in results:
        category = hit.payload.get("field")
        # try:
        #     print(
        #         f"[DEBUG] 3. Hit: score={hit.score:.4f}, "
        #         f"category={category}, "
        #         f"text={(hit.payload.get('preview_text') or hit.payload.get('context_full_preview', ''))[:30]}...",
        #         flush=True,
        #     )
        # except Exception:
        #     print("[DEBUG] Hit: <error printing hit>")

        if category:
            category_scores[category] += hit.score  # score 기반 가중

    total = sum(category_scores.values())

    print(f"[DEBUG] Aggregated category_scores: {dict(category_scores)}", flush=True)

    if total > 0:
        return {k: v / total for k, v in category_scores.items()}

    return {}


# 저장
def insert_point(point_id, vector, payload):
    client = get_qdrant_client()

    client.upsert(
        collection_name="context_block_v1",
        points=[
            {
                "id": point_id,
                "vector": vector,
                "payload": payload,
            }
        ],
    )
