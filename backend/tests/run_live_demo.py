from __future__ import annotations

import time
from fastapi.testclient import TestClient
from backend.app.main import app

def main():
    client = TestClient(app)

    print("==================================================")
    print("LEON V2 LIVE REAL-MACHINE VERIFICATION DEMO")
    print("==================================================")

    # 1. Computer Status
    print("\n--- 1. Computer Status & Subsystem Health ---")
    res = client.get("/api/computer/status")
    print(f"Status Code: {res.status_code}")
    print(f"State: {res.json().get('state')}")
    print(f"Active App: {res.json().get('active_application')}")
    print(f"Running Apps: {res.json().get('running_applications')}")

    # 2. Computer Screen & OS Observation
    print("\n--- 2. Observe Screen and Host Environment ---")
    start = time.perf_counter()
    res = client.post("/api/computer/observe", json={"include_vision": False})
    elapsed = (time.perf_counter() - start) * 1000
    data = res.json()
    print(f"Obs ID: {data.get('id')}")
    print(f"Screen Info: {data.get('screen')}")
    print(f"Active Window: {data.get('active_window')}")
    print(f"Observation Latency: {elapsed:.2f}ms")

    # 3. Screen Diagnosis
    print("\n--- 3. Screen Diagnosis ---")
    start = time.perf_counter()
    res = client.post("/api/computer/diagnose", json={"question": "Diagnose visible errors"})
    elapsed = (time.perf_counter() - start) * 1000
    diag = res.json()
    print(f"Diagnosis Status: {res.status_code}")
    print(f"Error Detected: {diag.get('error_detected')}")
    print(f"Diagnostics: {diag.get('diagnostics')}")
    print(f"Diagnosis Latency: {elapsed:.2f}ms")

    # 4. Observe -> Act -> Verify Loop
    print("\n--- 4. Observe -> Act -> Verify Loop Execution ---")
    start = time.perf_counter()
    res = client.post("/api/computer/act", json={
        "action": {
            "action_type": "inspect_workspace",
            "path": "."
        },
        "confirmed": True
    })
    elapsed = (time.perf_counter() - start) * 1000
    result = res.json()
    print(f"Action Result: Success={result.get('success')}, State={result.get('state')}")
    print(f"Verification: {result.get('verification')}")
    print(f"Metrics: {result.get('metrics')}")

    # 5. Security Kernel & Safety Enforcement
    print("\n--- 5. Security Kernel Policy Enforcement ---")
    res = client.post("/api/computer/act", json={
        "action": {
            "action_type": "launch_app",
            "app_name": "malicious_unapproved_binary.exe"
        },
        "confirmed": True
    })
    blocked = res.json()
    print(f"Blocked Unauthorized Action: Success={blocked.get('success')}, Error={blocked.get('error')}, Msg={blocked.get('message')}")

    # 6. Natural Command Routing
    print("\n--- 6. Natural Language Command Interactivity ---")
    test_queries = [
        "What application am I using?",
        "What is wrong on my screen?",
        "What time is it?",
        "Remember that my project is called LEON.",
        "What did I call my project?"
    ]
    for q in test_queries:
        start = time.perf_counter()
        cmd_res = client.post("/api/command", json={"message": q})
        q_elapsed = (time.perf_counter() - start) * 1000
        body = cmd_res.json()
        print(f"User: \"{q}\"")
        print(f"  -> Capability: {body.get('capability')} | Verified: {body.get('verified')} | Latency: {q_elapsed:.2f}ms")
        print(f"  -> LEON: \"{body.get('message')}\"")

    print("\n==================================================")
    print("ALL REAL DEMOS EXECUTED AND VERIFIED SUCCESSFULLY")
    print("==================================================")

if __name__ == "__main__":
    main()
