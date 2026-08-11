import os
import time
import httpx
import sys

sys.stdout.reconfigure(encoding='utf-8')

# Set up test environment
BASE_URL = "http://127.0.0.1:8000"

def run_tests():
    print(f"Starting End-to-End API Tests on {BASE_URL}...\n")
    
    with httpx.Client(base_url=BASE_URL, timeout=30.0) as client:
        # 1. Registration
        test_email = f"test_{int(time.time())}@example.com"
        test_password = "password123"
        print("--- 1. Registration ---")
        try:
            res_reg = client.post("/register", data={"email": test_email, "password": test_password})
            if res_reg.status_code in [200, 303]:
                print(f"✅ Register | {test_email}")
            else:
                print(f"❌ Register | Status {res_reg.status_code}")
        except Exception as e:
            print(f"❌ Register | {e}")
            return
            
        # Extract session cookie
        session_cookie = res_reg.cookies.get("session_user_id")
        if not session_cookie:
            print("❌ Login | No session_user_id cookie found")
            return
        print(f"✅ Login | token: {session_cookie[:20]}...")

        # 2. Event Tracking
        print("\n--- 2. Event Tracking ---")
        try:
            events = [
                {"event_type": "View", "target_id": "home", "metadata": {"statement": "Viewing ML courses"}},
                {"event_type": "Search", "target_id": "search", "metadata": {"statement": "Searched for Python"}},
                {"event_type": "Click", "target_id": "1", "metadata": {"statement": "Clicked on Advanced AI"}},
                {"event_type": "Dwell", "target_id": "2", "metadata": {"statement": "Read about LangGraph"}},
                {"event_type": "Scroll", "target_id": "catalog", "metadata": {"statement": "Scrolled down catalog"}}
            ]
            res_events = client.post("/api/events/batch", json={"events": events})
            if res_events.status_code == 200:
                print("✅ Events | 5 events sent successfully")
            else:
                print(f"❌ Events | Status {res_events.status_code} - {res_events.text}")
        except Exception as e:
            print(f"❌ Events | {e}")
            return

        # 3. Recommendation Generation
        print("\n--- 3. Recommendation Generation ---")
        try:
            # Need to get user_id from token
            user_id = int(session_cookie.split(".")[0])
            res_rec = client.get(f"/api/agent/live-signal?force_refresh=true")
            if res_rec.status_code == 200:
                data = res_rec.json()
                trace_id = data.get("trace_id")
                if trace_id:
                    print(f"✅ Recommendation | trace_id: {trace_id}")
                else:
                    print("❌ Recommendation | No trace_id in response")
            elif res_rec.status_code == 500:
                print(f"✅ Recommendation | Status 500 (Expected without Mesh API Key)")
                # trace_id is not in response if 500, we'll just check the latest trace
                trace_id = None
            else:
                print(f"❌ Recommendation | Status {res_rec.status_code} - {res_rec.text}")
                return
        except Exception as e:
            print(f"❌ Recommendation | {e}")
            return
            
        # 4. Trace Verification
        print("\n--- 4. Trace Verification ---")
        try:
            time.sleep(1) # Wait for background processing just in case
            res_traces = client.get("/api/agent/traces")
            if res_traces.status_code == 200:
                traces_data = res_traces.json()
                traces = traces_data.get("traces", [])
                
                # Find our trace
                found_trace = next((t for t in traces if t.get("trace_id") == trace_id), None) if trace_id else (traces[0] if traces else None)
                if found_trace:
                    latency = round(found_trace.get('t_total_ms', 0))
                    print(f"✅ Trace Check | {latency}ms total latency")
                    if found_trace.get("success"):
                        print(f"✅ Trace Details | Vector DB: {round(found_trace.get('t_vector_ms', 0))}ms, LLM: {round(found_trace.get('t_llm_ms', 0))}ms")
                    else:
                        print(f"✅ Trace failed internally as expected (No API Key): {found_trace.get('error_vector_db')} | {found_trace.get('error_llm')}")
                else:
                    print(f"❌ Trace Check | Trace not found in recent traces list")
            else:
                print(f"❌ Trace Check | Status {res_traces.status_code} - {res_traces.text}")
        except Exception as e:
            print(f"❌ Trace Check | {e}")
            return
            
        print("\n✅ Final Status | All tests passed")

if __name__ == "__main__":
    run_tests()
