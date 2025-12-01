import json
import os
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Any
from pymongo import MongoClient

# 설정
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("MONGO_DB_NAME", "sentencify")
OUTPUT_FILE = Path("personas.json")

def connect_db():
    client = MongoClient(MONGO_URI)
    return client[DB_NAME]

def analyze_personas(min_actions: int = 5) -> List[Dict[str, Any]]:
    """
    raw_corporate_data를 분석하여 유의미한 행동 패턴을 가진 페르소나를 추출합니다.
    """
    db = connect_db()
    collection = db["raw_corporate_data"]

    # 1. 사용자별 데이터 집계
    # event_raw.json의 데이터는 distinct_id를 가짐
    # correction_history.json의 데이터는 user 필드를 가짐
    
    print("[Info] Aggregating user behaviors...")
    
    user_stats = defaultdict(lambda: {
        "categories": Counter(),
        "intensities": Counter(),
        "languages": Counter(),
        "prompts": [],
        "action_count": 0,
        "accept_count": 0
    })

    # event_raw 처리 (실행, 선택 로그)
    cursor = collection.find({"_source_file": "event_raw.json"})
    for doc in cursor:
        user_id = doc.get("distinct_id")
        if not user_id:
            continue
            
        event = doc.get("event")
        
        if event == "event_editor_run_paraphrasing":
            user_stats[user_id]["action_count"] += 1
            if field := doc.get("field"):
                user_stats[user_id]["categories"][field] += 1
            if maintenance := doc.get("maintenance"):
                user_stats[user_id]["intensities"][maintenance] += 1
            if lang := doc.get("target_language"):
                user_stats[user_id]["languages"][lang] += 1

        elif event == "event_editor_selected_paraphrasing":
            if doc.get("was_accepted"):
                user_stats[user_id]["accept_count"] += 1

    # correction_history 처리 (User Prompts 추출용)
    cursor = collection.find({"_source_file": "correction_history.json"})
    for doc in cursor:
        user_id = doc.get("user")
        if not user_id:
            continue
        
        # correction_history도 하나의 액션으로 간주 (중복될 수 있으나 패턴 파악용)
        user_stats[user_id]["action_count"] += 1
        
        if field := doc.get("field"):
            user_stats[user_id]["categories"][field] += 1
        if intensity := doc.get("intensity"):
            user_stats[user_id]["intensities"][intensity] += 1
            
        if prompt := doc.get("user_prompt"):
            # 너무 긴 프롬프트는 제외 (간단한 스타일 지시만 추출)
            if len(prompt) < 50:
                user_stats[user_id]["prompts"].append(prompt)

    print(f"[Info] Found {len(user_stats)} distinct users.")

    # 2. 페르소나 추출 (Rule-based Clustering)
    # 단순하게 사용자가 가장 많이 쓴 속성을 해당 사용자의 페르소나로 정의
    personas = []
    
    for user_id, stats in user_stats.items():
        if stats["action_count"] < min_actions:
            continue

        # 가장 많이 쓴 카테고리 (Top 1)
        top_category = stats["categories"].most_common(1)
        category = top_category[0][0] if top_category else "general"
        
        # 가장 많이 쓴 강도
        top_intensity = stats["intensities"].most_common(1)
        intensity = top_intensity[0][0] if top_intensity else "moderate"
        
        # 언어
        top_lang = stats["languages"].most_common(1)
        language = top_lang[0][0] if top_lang else "ko"

        # 자주 쓴 프롬프트 (Top 3)
        top_prompts = [p for p, c in Counter(stats["prompts"]).most_common(3)]
        
        # 수락률
        accept_rate = stats["accept_count"] / stats["action_count"] if stats["action_count"] > 0 else 0.0

        # 이름 생성 (예: Thesis_Strong_Writer)
        persona_name = f"{category.capitalize()}_{intensity.capitalize()}_{language.upper()}"
        
        personas.append({
            "persona_id": f"persona_{user_id[:8]}",  # 익명화된 ID
            "base_user_id": user_id,
            "name": persona_name,
            "preferred_category": category,
            "preferred_intensity": intensity,
            "preferred_language": language,
            "common_prompts": top_prompts,
            "accept_rate_target": min(max(accept_rate, 0.3), 0.9), # 0.3 ~ 0.9 사이로 보정
            "total_actions_observed": stats["action_count"]
        })

    # 3. 대표 페르소나 선정 (중복 패턴 제거 및 Top N 선정)
    # 카테고리-강도 조합별로 가장 활동량이 많은 대표 페르소나 1명씩 선정
    unique_personas = {}
    for p in personas:
        key = f"{p['preferred_category']}_{p['preferred_intensity']}"
        if key not in unique_personas or p["total_actions_observed"] > unique_personas[key]["total_actions_observed"]:
            unique_personas[key] = p
    
    final_personas = list(unique_personas.values())
    
    # Fallback: 페르소나가 너무 적으면 기본 페르소나 추가
    if len(final_personas) < 3:
        print("[Warn] Not enough patterns found. Adding default personas.")
        defaults = [
            {"name": "Thesis_Strong_User", "preferred_category": "thesis", "preferred_intensity": "strong", "preferred_language": "ko", "accept_rate_target": 0.8},
            {"name": "Email_Moderate_User", "preferred_category": "email", "preferred_intensity": "moderate", "preferred_language": "ko", "accept_rate_target": 0.6},
            {"name": "Article_Weak_User", "preferred_category": "article", "preferred_intensity": "weak", "preferred_language": "en", "accept_rate_target": 0.5}
        ]
        for d in defaults:
            d["persona_id"] = f"persona_default_{d['preferred_category']}"
            d["common_prompts"] = []
            final_personas.append(d)

    print(f"[Info] Extracted {len(final_personas)} unique personas.")
    
    # 저장
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(final_personas, f, indent=2, ensure_ascii=False)
    
    print(f"✅ [Done] Saved to {OUTPUT_FILE}")

if __name__ == "__main__":
    analyze_personas()
