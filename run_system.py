"""
Samsung Innovation Campus (SIC8) - IoT Track
Master Runner for Industrial IoT Simulation & Gateway System
Launches:
  1. Raspberry Pi IoT Gateway (MQTT + TCP + UDP + Blynk + HTTP REST & Web Dashboard)
  2. Multi-Machine Software Simulator (Machines 1 to 5)
"""

import os
import subprocess
import sys
import time

def main():
    print("=" * 70)
    print("  SAMSUNG INNOVATION CAMPUS (SIC8) - INDUSTRIAL IOT SYSTEM RUNNER")
    print("  Software-Only Simulation (Machines 1-5) & Raspberry Pi IoT Gateway")
    print("=" * 70)

    base_dir = os.path.dirname(os.path.abspath(__file__))
    gateway_script = os.path.join(base_dir, "raspberry-gateway.py")
    simulation_script = os.path.join(base_dir, "simulation_machines.py")

    py_exe = sys.executable

    print("\n[1/2] Starting Raspberry Pi IoT Gateway...")
    gw_proc = subprocess.Popen([py_exe, gateway_script])

    # Wait 2 seconds for gateway servers (TCP 6000, UDP 7000, HTTP 8080) to initialize
    time.sleep(2.0)

    print("\n[2/2] Starting Multi-Machine Software Simulator (Machines 1 -> 5)...")
    sim_proc = subprocess.Popen([py_exe, simulation_script])

    print("\n" + "=" * 70)
    print("  SYSTEM IS FULLY OPERATIONAL!")
    print("  - Local Dashboard:      http://localhost:8080")
    print("  - Deployed Dashboard:   https://iotnexa-sic.web.app/index.html")
    print("  - Blynk Cloud App:      Token T-fb4daK... (V0: Temp, V1: Vib, V2: Prox, V3: Speed, V4: Start/Stop)")
    print("  - Protocols Active:     MQTT (HiveMQ) | TCP (Port 6000) | UDP (Port 7000)")
    print("  Press Ctrl+C to stop all components.")
    print("=" * 70 + "\n")

    try:
        while True:
            # Check if any process terminated unexpectedly
            if gw_proc.poll() is not None:
                print(f"[ERROR] Gateway exited unexpectedly with code {gw_proc.returncode}")
                break
            if sim_proc.poll() is not None:
                print(f"[ERROR] Simulation exited unexpectedly with code {sim_proc.returncode}")
                break
            time.sleep(1.0)
    except KeyboardInterrupt:
        print("\nShutting down IoT simulation & Gateway processes...")
    finally:
        for p, name in [(sim_proc, "Simulation"), (gw_proc, "Gateway")]:
            if p.poll() is None:
                print(f"Terminating {name}...")
                p.terminate()
                try:
                    p.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    p.kill()
        print("All processes stopped successfully.")

if __name__ == "__main__":
    main()
