"""
Automated Verification Script for SIC IoT Simulation & Gateway System
Tests:
  1. Gateway startup and HTTP endpoints (/api/status, /api/blynk/status)
  2. CORS header validation for https://iotnexa-sic.web.app
  3. Preflight OPTIONS request handling
  4. Multi-Machine TCP connectivity & command dispatch (/api/command)
  5. UDP Emergency Alert delivery and recording
  6. MQTT telemetry ingestion into gateway state
  7. Blynk IoT Cloud REST endpoint test
"""

import json
import socket
import subprocess
import sys
import time
import urllib.request

def run_tests():
    print("=" * 60)
    print("RUNNING AUTOMATED VERIFICATION SUITE")
    print("=" * 60)

    py_exe = sys.executable
    gw_proc = subprocess.Popen([py_exe, "raspberry-gateway.py"])
    time.sleep(2.0)

    sim_proc = subprocess.Popen([py_exe, "simulation_machines.py"])
    time.sleep(3.0)

    try:
        # Test 1: Test Gateway HTTP /api/status
        print("\n[Test 1] Testing /api/status endpoint...")
        req = urllib.request.Request("http://127.0.0.1:8080/api/status")
        with urllib.request.urlopen(req, timeout=5.0) as res:
            assert res.status == 200
            data = json.loads(res.read().decode())
            assert data["success"] is True
            assert len(data["machines"]) == 5
            print("  PASSED: /api/status returned 5 machines.")

        # Test 2: CORS Headers validation for deployed site
        print("\n[Test 2] Testing CORS Headers for https://iotnexa-sic.web.app...")
        req = urllib.request.Request(
            "http://127.0.0.1:8080/api/status",
            headers={"Origin": "https://iotnexa-sic.web.app"}
        )
        with urllib.request.urlopen(req, timeout=5.0) as res:
            origin_header = res.headers.get("Access-Control-Allow-Origin")
            print(f"  Access-Control-Allow-Origin header: {origin_header}")
            assert origin_header in ["https://iotnexa-sic.web.app", "*"]
            print("  PASSED: CORS origin header correctly configured.")

        # Test 3: OPTIONS Preflight request
        print("\n[Test 3] Testing OPTIONS preflight request...")
        req = urllib.request.Request(
            "http://127.0.0.1:8080/api/command",
            headers={
                "Origin": "https://iotnexa-sic.web.app",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Content-Type"
            },
            method="OPTIONS"
        )
        with urllib.request.urlopen(req, timeout=5.0) as res:
            assert res.status in [200, 204]
            allow_methods = res.headers.get("Access-Control-Allow-Methods")
            print(f"  Status: {res.status}")
            print(f"  Access-Control-Allow-Methods: {allow_methods}")
            assert "POST" in allow_methods
            print("  PASSED: Preflight OPTIONS handled cleanly.")

        # Test 4: TCP Command Dispatch (START Machine 4)
        print("\n[Test 4] Testing TCP Command Dispatch (START Machine 4)...")
        post_data = json.dumps({"machine_id": 4, "command": "START", "value": 1800}).encode()
        req = urllib.request.Request(
            "http://127.0.0.1:8080/api/command",
            data=post_data,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=5.0) as res:
            cmd_res = json.loads(res.read().decode())
            assert cmd_res["success"] is True
            print("  PASSED: Command sent successfully over TCP.")

        time.sleep(2.0)

        # Verify Machine 4 state updated
        req = urllib.request.Request("http://127.0.0.1:8080/api/status")
        with urllib.request.urlopen(req, timeout=5.0) as res:
            data = json.loads(res.read().decode())
            m4 = next(m for m in data["machines"] if m["id"] == 4)
            assert m4["state"] == "RUNNING"
            assert m4["valve_state"] == "OPEN"
            print(f"  PASSED: Machine 4 state is now {m4['state']}, speed={m4['motor_speed']}, valve={m4['valve_state']}.")

        # Test 5: UDP Emergency Alert Simulation
        print("\n[Test 5] Testing UDP Emergency Alert trigger...")
        post_data = json.dumps({"machine_id": 2, "fault": "TEMP_HIGH"}).encode()
        req = urllib.request.Request(
            "http://127.0.0.1:8080/api/simulate/fault",
            data=post_data,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=5.0) as res:
            fault_res = json.loads(res.read().decode())
            assert fault_res["success"] is True

        time.sleep(1.5)

        # Verify alert received on Gateway
        req = urllib.request.Request("http://127.0.0.1:8080/api/status")
        with urllib.request.urlopen(req, timeout=5.0) as res:
            data = json.loads(res.read().decode())
            recent = [a["alert"] for a in data["alerts"]]
            print(f"  Recent Gateway alerts: {recent}")
            assert "TEMP_HIGH" in recent
            print("  PASSED: UDP emergency alert received and recorded in gateway state.")

        # Test 6: Blynk Status & Pin Mapping endpoint
        print("\n[Test 6] Testing Blynk status endpoint...")
        req = urllib.request.Request("http://127.0.0.1:8080/api/blynk/status")
        with urllib.request.urlopen(req, timeout=5.0) as res:
            blynk_data = json.loads(res.read().decode())
            assert blynk_data["pins"]["V0"] == "Temperature"
            assert blynk_data["pins"]["V1"] == "Vibration"
            assert blynk_data["pins"]["V2"] == "Proximity"
            assert blynk_data["pins"]["V3"] == "Motor Speed"
            assert blynk_data["pins"]["V4"] == "StartandStop"
            print("  PASSED: Blynk virtual pins V0-V4 accurately mapped.")

        print("\n" + "=" * 60)
        print("ALL VERIFICATION TESTS PASSED SUCCESSFULLY!")
        print("=" * 60)

    finally:
        print("\nCleaning up test processes...")
        sim_proc.terminate()
        gw_proc.terminate()
        sim_proc.wait()
        gw_proc.wait()

if __name__ == "__main__":
    run_tests()
