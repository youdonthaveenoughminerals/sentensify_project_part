import time
import uuid
import json
import random
import requests
from datetime import datetime, timezone

# Configuration
API_URL = "http://localhost:8000/log"
USER_ID = "live_test"  # Fixed user for targeted dashboard testing

# Use a persistent session for efficiency
session = requests.Session()

def _now_iso():
    return datetime.now(timezone.utc).isoformat()

def send_log(event_name, payload):
    """Send log event to API via HTTP POST."""
    payload["event"] = event_name
    if "created_at" not in payload:
        payload["created_at"] = _now_iso()
    
    try:
        # The API expects the entire payload in the body
        # including the 'event' field to route it.
        resp = session.post(API_URL, json=payload, timeout=2)
        if resp.status_code != 200:
            print(f"❌ Failed to send {event_name}: {resp.status_code} {resp.text}")
        else:
            print(f"✅ Sent {event_name}: {resp.json()}")
    except Exception as e:
        print(f"❌ Error sending {event_name}: {e}")

def simulate():
    print(f"🚀 Starting HTTP Traffic Simulator (Target: {API_URL})")
    print(f"👤 User ID: {USER_ID}")
    print("Press Ctrl+C to stop.\n")

    doc_id = str(uuid.uuid4())
    
    try:
        while True:
            # Session Context
            session_id = str(uuid.uuid4())
            insert_id = str(uuid.uuid4())
            
            # 1. A Event (View/Recommend)
            # API normally generates this on /recommend, but we simulate the LOG here.
            # Note: API /recommend endpoint generates A log internally. 
            # To simulate 'external' logs or just noise, we use /log.
            # Ideally we should call /recommend to test full flow, but the prompt asks to use /log.
            a_payload = {
                "insert_id": insert_id,
                "recommend_session_id": session_id,
                "doc_id": doc_id,
                "user_id": USER_ID,
                "reco_category_input": random.choice(["email", "report", "thesis"]),
                "latency_ms": random.randint(100, 2500), # Some high latency
                "model_version": "sim_v1"
            }
            # Note: 'editor_recommend_options' is usually internal to API, but /log allows it.
            # Wait, standard flow is /recommend -> A log. 
            # But let's follow prompt to use /log for simulation to pump data.
            # Actually, for A event, usually we want to see it in the dashboard. 
            # The prompt says "A, B, C, E, K events".
            # We'll send 'recommend_log' (I) as well which is used for stats.
            
            # To fix the "Dashboard not updating" issue, we need A events in MongoDB.
            # The API's /log endpoint handles:
            # - editor_run_paraphrasing (B)
            # - editor_selected_paraphrasing (C)
            # - editor_document_snapshot (K)
            # - others -> others.jsonl
            
            # Wait, looking at main.py code I just wrote:
            # if event == "editor_run_paraphrasing": ...
            # elif event == "editor_selected_paraphrasing": ...
            # elif event == "editor_document_snapshot": ...
            # else: others.jsonl
            
            # !! CRITICAL !!
            # The current API /log implementation dumps 'editor_recommend_options' (A) into 'others.jsonl'.
            # It does NOT insert into MongoDB collection 'editor_recommend_options'.
            # This means this simulator using /log for A events won't populate the DB for A events if the API doesn't handle it.
            
            # However, the prompt says: "Fix Simulator... requests.post(API_URL...)"
            # If the API doesn't support A events via /log, we should either:
            # 1. Call /recommend (Real flow)
            # 2. Update API to handle A events in /log
            # 3. Just simulate B/C/K/E and hope A is not strict dependency (but Funnel needs A).
            
            # Let's assume for this task we should call the real endpoints where possible?
            # Or better, let's stick to the instruction but acknowledge A might go to 'others' unless we update main.py.
            # BUT, looking at the previous context, the goal is to verify ingestion.
            # If I use /recommend, it does A+I+E + DB Insert.
            # If I use /log for B/C/K, it does DB Insert. 
            
            # REVISED STRATEGY:
            # To ensure A events appear in Dashboard (which reads Mongo), we MUST call POST /recommend.
            # Calling /log with event="editor_recommend_options" will land in "others" collection/file based on current main.py.
            # So, I will simulate A by calling /recommend, and B/C/K by calling /log. 
            
            # 1. Call /recommend (Generates A, I, E in DB)
            rec_req = {
                "doc_id": doc_id,
                "user_id": USER_ID,
                "selected_text": "This is a simulation text.",
                "field": "email"
            }
            try:
                res = session.post("http://localhost:8000/recommend", json=rec_req)
                if res.status_code == 200:
                    data = res.json()
                    session_id = data["recommend_session_id"]
                    source_id = data["insert_id"]
                    print(f"✅ Sent /recommend (A+I+E): {session_id}")
                else:
                    print(f"❌ /recommend failed: {res.text}")
                    continue # Skip rest if A failed
            except Exception as e:
                print(f"❌ /recommend error: {e}")
                continue

            time.sleep(0.5)

            # 2. B Event (Run) via /log
            b_payload = {
                "recommend_session_id": session_id,
                "source_recommend_event_id": source_id,
                "doc_id": doc_id,
                "user_id": USER_ID,
                "target_category": "email",
                "target_language": "en",
                "target_intensity": "strong"
            }
            send_log("editor_run_paraphrasing", b_payload)
            
            time.sleep(0.5)

            # 3. C Event (Accept) via /log - 50% chance
            if random.random() > 0.5:
                c_payload = {
                    "recommend_session_id": session_id,
                    "source_recommend_event_id": source_id,
                    "doc_id": doc_id,
                    "user_id": USER_ID,
                    "was_accepted": True,
                    "selected_option_index": 0
                }
                send_log("editor_selected_paraphrasing", c_payload)
                print("   (Accepted)")
            else:
                print("   (Rejected/Ignored)")

            # 4. K Event (Snapshot) - every few loops
            if random.random() > 0.8:
                k_payload = {
                    "doc_id": doc_id,
                    "user_id": USER_ID,
                    "full_text": "Updated full text content " + str(time.time())
                }
                send_log("editor_document_snapshot", k_payload)

            time.sleep(1)

    except KeyboardInterrupt:
        print("\n🛑 Simulation stopped.")

if __name__ == "__main__":
    simulate()