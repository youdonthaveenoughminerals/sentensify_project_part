import json
import time
import requests
from pathlib import Path

# 설정
BASE_DIR = Path(__file__).parent.parent
SCENARIO_FILE = BASE_DIR / "mock_golden_scenario.json"
API_URL = "http://localhost:8000"

def load_scenario():
    with open(SCENARIO_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def play_scenario():
    if not SCENARIO_FILE.exists():
        print(f"Error: {SCENARIO_FILE} not found. Run 'generate_golden_scenario.py' first.")
        return

    scenarios = load_scenario()
    print(f"Loaded {len(scenarios)} sessions. Starting playback...")

    for i, session in enumerate(scenarios):
        print(f"\n--- Session {i+1}/{len(scenarios)}: {session['user_id']} ({session['persona_id']}) ---")
        
        # Context
        text = session["text"]
        doc_id = session["doc_id"]
        user_id = session["user_id"]
        
        # State
        last_reco_id = None
        last_insert_id = None
        last_reco_options = [] # Store options from A

        for action in session["actions"]:
            atype = action["type"]
            
            if atype == "recommend":
                # Call /recommend
                payload = {
                    "doc_id": doc_id,
                    "user_id": user_id,
                    "selected_text": text,
                    "context_prev": "",
                    "context_next": ""
                }
                try:
                    res = requests.post(f"{API_URL}/recommend", json=payload)
                    if res.status_code == 200:
                        data = res.json()
                        last_reco_id = data["recommend_session_id"]
                        last_insert_id = data["insert_id"]
                        last_reco_options = data.get("reco_options", [])
                        print(f"  [API] Recommend OK. Options: {len(last_reco_options)}")
                    else:
                        print(f"  [API] Recommend Failed: {res.status_code}")
                except Exception as e:
                    print(f"  [API] Request Error: {e}")
            
            elif atype == "paraphrase":
                # Determine options
                opts = action["options"]
                final_cat = ""
                final_int = ""
                final_lang = ""

                if opts.get("use_recommendation") and last_reco_options:
                    # Use recommended option (Top-1)
                    top1 = last_reco_options[0]
                    final_cat = top1.get("category", "none")
                    final_int = top1.get("intensity", "moderate")
                    final_lang = top1.get("language", "ko") # Default if missing
                    print(f"  -> Using Recommendation: {final_cat}/{final_int}")
                else:
                    # Use persona preference
                    final_cat = opts.get("category", "none")
                    final_int = opts.get("intensity", "moderate")
                    final_lang = opts.get("language", "ko")
                    print(f"  -> Using User Pref: {final_cat}/{final_int}")

                # Call /paraphrase
                payload = {
                    "doc_id": doc_id,
                    "user_id": user_id,
                    "selected_text": text,
                    "category": final_cat,
                    "language": final_lang,
                    "intensity": final_int,
                    "recommend_session_id": last_reco_id,
                    "source_recommend_event_id": last_insert_id
                }
                try:
                    res = requests.post(f"{API_URL}/paraphrase", json=payload)
                    if res.status_code == 200:
                        print(f"  [API] Paraphrase OK (Run).")
                    else:
                        print(f"  [API] Paraphrase Failed: {res.status_code}")
                except Exception as e:
                    print(f"  [API] Request Error: {e}")

            elif atype == "select":
                # Call /log (Simulate Selection)
                # Note: The API endpoint for selection logic is actually handled by the frontend calling /log
                # with event='editor_selected_paraphrasing'.
                payload = {
                    "event": "editor_selected_paraphrasing",
                    "doc_id": doc_id,
                    "user_id": user_id,
                    "recommend_session_id": last_reco_id,
                    "source_recommend_event_id": last_insert_id,
                    "was_accepted": action["accepted"],
                    "selected_option_index": 0
                }
                try:
                    res = requests.post(f"{API_URL}/log", json=payload)
                    if res.status_code == 200:
                        print(f"  [API] Select OK (Log).")
                    else:
                        print(f"  [API] Select Log Failed: {res.status_code}")
                except Exception as e:
                    print(f"  [API] Request Error: {e}")

            time.sleep(0.1) # Rate limit
        
        time.sleep(0.5) # Session gap

if __name__ == "__main__":
    play_scenario()
