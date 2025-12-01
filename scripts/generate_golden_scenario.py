import json
import random
import uuid
import csv
from pathlib import Path

# 설정
BASE_DIR = Path(__file__).parent.parent
PERSONA_FILE = BASE_DIR / "data" / "personas.json"
DATA_FILE = BASE_DIR / "api" / "test_data.csv"
OUTPUT_FILE = BASE_DIR / "mock_golden_scenario.json"

SESSION_COUNT = 100  # 생성할 총 세션 수

def load_personas():
    with open(PERSONA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def load_sentences():
    sentences = []
    if not DATA_FILE.exists():
        print(f"⚠️ {DATA_FILE} not found. Using dummy sentences.")
        return [{"text": "This is a dummy sentence.", "label": "thesis"}]
    
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if "text" in row and "label" in row:
                sentences.append(row)
    return sentences

def generate_scenario():
    personas = load_personas()
    all_sentences = load_sentences()
    
    scenarios = []
    
    for _ in range(SESSION_COUNT):
        # 1. Pick Persona
        persona = random.choices(personas, weights=[p["weight"] for p in personas], k=1)[0]
        
        # 2. Pick Sentence (Context)
        # 페르소나 선호 카테고리와 일치하는 문장 필터링
        candidates = [s for s in all_sentences if s["label"] in persona["preference"]["categories"]]
        if not candidates:
            candidates = all_sentences # Fallback
        
        target_content = random.choice(candidates)
        
        # 3. Define Actions
        user_id = f"sim_{persona['id']}_{str(uuid.uuid4())[:8]}"
        doc_id = str(uuid.uuid4())
        
        session_data = {
            "user_id": user_id,
            "doc_id": doc_id,
            "text": target_content["text"],
            "ground_truth_category": target_content["label"],
            "persona_id": persona["id"],
            "actions": []
        }
        
        # 3. Define Flow based on probabilities
        probs = persona["behavior_probs"]
        rand_val = random.random()
        
        flow_type = "no_action"
        if rand_val < probs["run_rate"]:
            # Run을 하긴 할 건데, 수정해서 할 거냐(modify_rate) 그대로 할 거냐?
            # (Note: modify_rate logic interpretation: probability to modify IF running)
            if random.random() < probs["modify_rate"]:
                flow_type = "modify_reco"
            else:
                flow_type = "accept_reco"
        
        # 4. Construct Actions
        session_data["expected_flow"] = flow_type
        
        # Action A: Recommend (Always)
        session_data["actions"].append({"type": "recommend"})
        
        if flow_type in ["accept_reco", "modify_reco"]:
            # Action B: Paraphrase
            # Crucial: Always use the Persona's PREFERRED Intensity and Language.
            # This ensures P_user learns "Scholar -> Strong", "Biz -> English".
            # Category is set to the Ground Truth (context label) to ensure valid input.
            
            run_opts = {
                "category": target_content["label"],
                "intensity": persona["preference"]["intensity"],
                "language": persona["preference"]["language"]
            }

            session_data["actions"].append({
                "type": "paraphrase",
                "options": run_opts
            })
            
            # Action C: Select
            if random.random() < probs["select_rate"]:
                session_data["actions"].append({
                    "type": "select",
                    "accepted": True
                })


        
        scenarios.append(session_data)
        
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(scenarios, f, indent=2, ensure_ascii=False)
        
    print(f"✅ Generated {len(scenarios)} scenarios at {OUTPUT_FILE}")

if __name__ == "__main__":
    generate_scenario()
