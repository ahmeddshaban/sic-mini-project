"""
Samsung Innovation Campus (SIC8) - IoT Track
24/7 Cloud & Local Industrial IoT System Runner
Supervises:
  1. Raspberry Pi IoT Gateway (MQTT + TCP + UDP + Blynk + HTTP REST & Web Dashboard)
  2. Multi-Machine Software Simulator (Machines 1 to 5)

Features for 24/7 Cloud Operation:
  - Automatic process resurrection / auto-restart on unexpected crashes
  - Graceful SIGINT and SIGTERM handling for Linux systemd / Docker / PM2
  - Environment variable configuration (PORT, HOST, BIND_IP)
  - Real-time supervisor uptime and crash recovery logging
"""

import os
import signal
import subprocess
import sys
import time

SHUTDOWN_REQUESTED = False

def handle_shutdown_signal(signum, frame):
    global SHUTDOWN_REQUESTED
    sig_name = "SIGINT" if signum == signal.SIGINT else "SIGTERM"
    print(f"\n[SUPERVISOR] Received {sig_name}. Initiating graceful 24/7 shutdown...")
    SHUTDOWN_REQUESTED = True

def spawn_process(name, cmd_args):
    print(f"[SUPERVISOR] Starting {name} ({' '.join(cmd_args)})...")
    return subprocess.Popen(cmd_args)

def main():
    global SHUTDOWN_REQUESTED

    # Register signals for clean termination on Windows and Linux (systemd / Docker)
    signal.signal(signal.SIGINT, handle_shutdown_signal)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, handle_shutdown_signal)

    base_dir = os.path.dirname(os.path.abspath(__file__))
    gateway_script = os.path.join(base_dir, "raspberry-gateway.py")
    simulation_script = os.path.join(base_dir, "simulation_machines.py")
    py_exe = sys.executable

    port = os.environ.get("PORT", os.environ.get("HTTP_PORT", "8080"))
    auto_restart = os.environ.get("AUTO_RESTART", "1").lower() not in ["0", "false", "no"]

    print("=" * 72)
    print("  SAMSUNG INNOVATION CAMPUS (SIC8) - INDUSTRIAL IOT SYSTEM RUNNER")
    print("  24/7 Cloud Server & Edge Simulation Engine (Machines 1-5)")
    print("=" * 72)
    print(f"  [Config] Gateway Web/REST Port: {port}")
    print(f"  [Config] 24/7 Auto-Restart Resilience: {'ENABLED' if auto_restart else 'DISABLED'}")
    print(f"  [Config] Python Executable: {py_exe}")
    print("-" * 72)

    # 1. Start Raspberry Pi Gateway
    gw_proc = spawn_process("Raspberry Pi IoT Gateway", [py_exe, gateway_script])
    time.sleep(2.0)

    # 2. Start Simulation Machines
    sim_proc = spawn_process("Multi-Machine Simulator", [py_exe, simulation_script])

    print("\n" + "=" * 72)
    print("  SYSTEM IS FULLY OPERATIONAL (24/7 Cloud Supervised Mode)")
    print(f"  - Web Dashboard:        http://0.0.0.0:{port} (or http://<cloud-ip>:{port})")
    print("  - Local Dashboard:      http://localhost:8080")
    print("  - Deployed Dashboard:   https://iotnexa-sic.web.app/index.html")
    print("  - Blynk Cloud App:      Token linked (V0: Temp, V1: Vib, V2: Prox, V3: Speed, V4: Start/Stop)")
    print("  - Protocols Active:     MQTT (HiveMQ) | TCP (Port 6000) | UDP (Port 7000)")
    print("  - Cloud Firewall Note:  Ensure ports 8080 (HTTP), 6000 (TCP), and 7000 (UDP)")
    print("                          are opened in your cloud security groups / firewall.")
    print("  Press Ctrl+C to stop all components.")
    print("=" * 72 + "\n")

    start_time = time.time()
    gw_restarts = 0
    sim_restarts = 0

    try:
        while not SHUTDOWN_REQUESTED:
            time.sleep(1.5)

            # Health check: Gateway Process
            if gw_proc.poll() is not None:
                ret = gw_proc.returncode
                print(f"[SUPERVISOR ALERT] Gateway exited with code {ret} at {time.strftime('%Y-%m-%d %H:%M:%S')}")
                if auto_restart and not SHUTDOWN_REQUESTED:
                    gw_restarts += 1
                    print(f"[SUPERVISOR] Auto-restarting Gateway in 2s (Restart #{gw_restarts})...")
                    time.sleep(2.0)
                    gw_proc = spawn_process("Raspberry Pi IoT Gateway", [py_exe, gateway_script])
                else:
                    break

            # Health check: Simulator Process
            if sim_proc.poll() is not None:
                ret = sim_proc.returncode
                print(f"[SUPERVISOR ALERT] Simulator exited with code {ret} at {time.strftime('%Y-%m-%d %H:%M:%S')}")
                if auto_restart and not SHUTDOWN_REQUESTED:
                    sim_restarts += 1
                    print(f"[SUPERVISOR] Auto-restarting Simulator in 2s (Restart #{sim_restarts})...")
                    time.sleep(2.0)
                    sim_proc = spawn_process("Multi-Machine Simulator", [py_exe, simulation_script])
                else:
                    break

    except KeyboardInterrupt:
        print("\n[SUPERVISOR] Interrupted by user.")
    finally:
        uptime = round(time.time() - start_time, 1)
        print(f"\n[SUPERVISOR] Shutting down. Total session uptime: {uptime}s (GW Restarts: {gw_restarts}, Sim Restarts: {sim_restarts})")
        for p, name in [(sim_proc, "Simulation"), (gw_proc, "Gateway")]:
            if p and p.poll() is None:
                print(f"[SUPERVISOR] Terminating {name}...")
                p.terminate()
                try:
                    p.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    print(f"[SUPERVISOR] Force killing {name}...")
                    p.kill()
        print("[SUPERVISOR] All processes terminated cleanly.")

if __name__ == "__main__":
    main()
