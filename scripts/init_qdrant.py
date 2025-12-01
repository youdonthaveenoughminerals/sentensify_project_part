import os
import sys

sys.path.append("/app")

import pandas as pd  # noqa: E402
from app.qdrant.collection import create_collection  # noqa: E402
from app.qdrant.init_data import insert_initial_data  # noqa: E402
from app.qdrant.init_correction import insert_correction_history_data  # noqa: E402


if __name__ == "__main__":
    print("=" * 50)
    print("Qdrant Collection 초기화 시작")
    print("=" * 50)

    # 0. 임베딩 모델 로딩
    print("\n[0/4] 임베딩 모델 로딩 중...")
    from app.utils.embedding import embedding_service  # noqa: E402

    embedding_service.load_model()
    print("✓ 모델 로딩 완료!")

    # 1. Context Block 컬렉션 생성
    print("\n[1/4] Context Block (E) 생성 중...")
    create_collection()
    print("✓ Collection 생성 완료!")

    # 2. Context Block 초기 데이터 삽입
    print("\n[2/4] Context Block 데이터 삽입 중...")

    csv_path = "/app/data/train_data.csv"
    if not os.path.exists(csv_path):
        print(f"⚠️  CSV 파일 없음: {csv_path}")
        print("테스트 샘플 데이터만 생성합니다.")
        df = pd.DataFrame(
            [
                {
                    "field": "thesis",
                    "content": "본 논문에서는 자연어 처리를 제안한다.",
                    "intensity": "strong",
                },
                {
                    "field": "email",
                    "content": "안녕하세요, 보고서 잘 받았습니다.",
                    "intensity": "weak",
                },
                {
                    "field": "report",
                    "content": "2024년 실적은 15% 증가했습니다.",
                    "intensity": "moderate",
                },
            ]
        )
    else:
        df = pd.read_csv(csv_path)

    print(f"총 {len(df)}개의 데이터를 삽입합니다.")

    batch_size = 500
    for start in range(0, len(df), batch_size):
        insert_initial_data(df.iloc[start : start + batch_size], start_id=start)
        print(f"진행: {min(start + batch_size, len(df))}/{len(df)}")
        
    # 3. Correction History 초기화 (NEW)
    print("\n[3/4] Correction History (D) 초기화 중...")
    insert_correction_history_data()

    # 4. 검증
    print("\n[4/4] 검증 중...")
    from app.qdrant.client import get_qdrant_client  # noqa: E402

    client = get_qdrant_client()
    
    info_ctx = client.get_collection("context_block_v1")
    print(f"✓ Collection: context_block_v1 (Count: {info_ctx.points_count})")
    
    try:
        info_corr = client.get_collection("correction_history_v1")
        print(f"✓ Collection: correction_history_v1 (Count: {info_corr.points_count})")
    except Exception:
        print("⚠️ Collection: correction_history_v1 not found.")

    print("\n" + "=" * 50)
    print("초기화 완료!")
    print("=" * 50)

