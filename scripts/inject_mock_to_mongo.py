import json
import pymongo
from datetime import datetime
from generate_golden_scenario import dataset  # 방금 만드신 스크립트에서 데이터셋 가져오기
# 혹은 위 dataset 변수를 그대로 복사해서 사용해도 됩니다.

# 1. MongoDB 연결 (Docker Compose 로컬 환경 가정)
client = pymongo.MongoClient("mongodb://localhost:27017/")
db = client["sentencify_db"]  # 프로젝트에서 사용하는 DB명 (확인 필요, 기본값 가정)

print(f"🔌 Connected to MongoDB: {db.name}")

def parse_date(date_str):
    if isinstance(date_str, str):
        # "2025-11-22T09:27:47.321954Z" 형식 파싱
        return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    return date_str

# 2. 컬렉션별 데이터 매핑 및 저장
def inject_data():
    data = dataset # generate_golden_scenario.py의 결과값

    # (1) Log A -> 'log_a' collection
    col_a = db["log_a"]
    doc_a = data["A"]
    doc_a["created_at"] = parse_date(doc_a["created_at"])
    col_a.insert_one(doc_a)
    print(f"✅ Log A Injected: {doc_a['insert_id']}")

    # (2) Log B -> 'log_b' collection
    col_b = db["log_b"]
    doc_b = data["B"]
    doc_b["created_at"] = parse_date(doc_b["created_at"])
    col_b.insert_one(doc_b)
    print(f"✅ Log B Injected: {doc_b['insert_id']}")

    # (3) Log C -> 'log_c' collection
    col_c = db["log_c"]
    doc_c = data["C"]
    doc_c["created_at"] = parse_date(doc_c["created_at"])
    col_c.insert_one(doc_c)
    print(f"✅ Log C Injected: {doc_c['insert_id']}")

    # (4) Ground Truth D -> 'correction_history' collection
    col_d = db["correction_history"]
    doc_d = data["D"]
    doc_d["created_at"] = parse_date(doc_d["created_at"])
    col_d.insert_one(doc_d)
    print(f"✅ Log D (History) Injected: {doc_d['_id']}")

    # (5) Context E -> 'context_block' collection
    col_e = db["context_block"]
    doc_e = data["E"]
    doc_e["created_at"] = parse_date(doc_e["created_at"])
    # Vector Search용이므로 context_hash가 PK 역할
    col_e.update_one(
        {"context_hash": doc_e["context_hash"]}, 
        {"$set": doc_e}, 
        upsert=True
    )
    print(f"✅ Context E Injected: {doc_e['context_hash']}")
    
    # (6) Full Document K (Phase 2 필수) -> 'full_document_store'
    # Golden Scenario에는 없지만 ETL을 위해 최소 데이터 생성
    col_k = db["full_document_store"]
    doc_k = {
        "doc_id": data["A"]["doc_id"],
        "latest_full_text": "안녕하세요. 이거 해줘 감사합니다.",
        "blocks": [
            {"block_index": 0, "text": "안녕하세요."},
            {"block_index": 1, "text": "이거 해줘"},
            {"block_index": 2, "text": "감사합니다."}
        ],
        "diff_ratio": 0.0,
        "last_synced_at": parse_date(data["A"]["created_at"])
    }
    col_k.update_one(
        {"doc_id": doc_k["doc_id"]},
        {"$set": doc_k},
        upsert=True
    )
    print(f"✅ Document K Injected: {doc_k['doc_id']}")

if __name__ == "__main__":
    try:
        inject_data()
        print("\n🎉 모든 Mock 데이터가 MongoDB에 적재되었습니다.")
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        print("Docker가 실행 중인지, 포트(27017)가 열려있는지 확인해주세요.")