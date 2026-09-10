"""
Samsung Innovation Campus (SIC8) - IoT Track
Unified Raspberry Pi IoT Gateway (Software Edition)
Integrates:
  - MQTT Ingestion (Telemetry from Machines 1 -> 5)
  - TCP Control Server (START/STOP, RESET, SET_SPEED)
  - UDP Alert Receiver (TEMP_HIGH, VIB_HIGH, SENSOR_FAULT)
  - Blynk IoT Cloud REST Integration (V0: Temp, V1: Vib, V2: Prox, V3: Speed, V4: Start/Stop)
  - CORS-enabled HTTP REST API & Web Dashboard on Port 8080 (serves https://iotnexa-sic.web.app)
"""

import json
import socket
import threading
import time
import urllib.parse
import urllib.request
from flask import Flask, jsonify, request, send_from_directory
import paho.mqtt.client as mqtt

NUM_MACHINES = 5

# --- Network & Protocol Configuration ---
MQTT_BROKER = "broker.hivemq.com"
MQTT_PORT = 1883
TOPIC_TELEMETRY = "sic_factory/machine/+/telemetry"

TCP_HOST = "0.0.0.0"
TCP_PORT = 6000

UDP_HOST = "0.0.0.0"
UDP_PORT = 7000

HTTP_HOST = "0.0.0.0"
HTTP_PORT = 8080

# --- Blynk IoT Configuration ---
BLYNK_AUTH_TOKEN = "vwxq7XgWR0BHbd-JSokS_FSuhh6XHp1o"
BLYNK_BASE_URL = "https://blynk.cloud/external/api"

VPIN_TEMPERATURE = "v0"
VPIN_VIBRATION = "v1"
VPIN_PROXIMITY = "v2"
VPIN_MOTOR_SPEED = "v3"
VPIN_START_STOP = "v4"

# --- Central State Storage ---
state_lock = threading.Lock()
blynk_active_machine = 1
last_blynk_v4_val = None

machines_state = {
    i: {
        "id": i,
        "temperature": 25.0 + (i * 2.5),
        "vibration": 15.0 + (i * 2.0),
        "proximity": 0,
        "motor_state": "STOPPED",
        "motor_speed": 0,
        "valve_state": "CLOSED",
        "state": "STOPPED",
        "connected_tcp": False,
        "alerts": [],
        "last_update": time.time(),
    }
    for i in range(1, NUM_MACHINES + 1)
}

recent_alerts = []
tcp_connections = {}  # machine_id -> socket connection


# ==========================================
# 1) MQTT Handler -> Machine Telemetry
# ==========================================
def on_mqtt_connect(client, userdata, flags, reason_code=None, properties=None):
    print(f"[MQTT Gateway] Connected to broker ({MQTT_BROKER}:{MQTT_PORT})")
    client.subscribe(TOPIC_TELEMETRY)
    # Also listen to legacy topic formats if any
    client.subscribe("factory/sensors/data")
    client.subscribe("factory/machine/+/sensors")


def on_mqtt_message(client, userdata, msg):
    try:
        topic = msg.topic
        payload = json.loads(msg.payload.decode("utf-8"))

        if "telemetry" in topic or "sensors" in topic:
            parts = topic.split("/")
            machine_id = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else payload.get("machine_id", 1)
            with state_lock:
                if machine_id in machines_state:
                    machines_state[machine_id].update({
                        "temperature": payload.get("temperature", machines_state[machine_id]["temperature"]),
                        "vibration": payload.get("vibration", machines_state[machine_id]["vibration"]),
                        "proximity": payload.get("proximity", machines_state[machine_id]["proximity"]),
                        "motor_state": payload.get("motor_state", machines_state[machine_id]["motor_state"]),
                        "motor_speed": payload.get("motor_speed", machines_state[machine_id]["motor_speed"]),
                        "valve_state": payload.get("valve_state", machines_state[machine_id]["valve_state"]),
                        "state": payload.get("state", machines_state[machine_id]["state"]),
                        "last_update": time.time(),
                    })
        elif topic == "factory/sensors/data" and isinstance(payload, list):
            # Legacy payload compatibility
            with state_lock:
                m1 = machines_state[1]
                for item in payload:
                    name = item.get("name")
                    val = item.get("value")
                    if name in m1:
                        m1[name] = val
                m1["last_update"] = time.time()
    except Exception as err:
        print(f"[MQTT Gateway] Parse error: {err}")


def run_mqtt_client():
    try:
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    except AttributeError:
        client = mqtt.Client()

    client.on_connect = on_mqtt_connect
    client.on_message = on_mqtt_message
    try:
        client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
        client.loop_forever()
    except Exception as err:
        print(f"[MQTT Gateway] Fatal connection error: {err}")


# ==========================================
# 2) TCP Server -> Bidirectional Control
# ==========================================
def handle_tcp_machine(conn, addr):
    machine_id = None
    try:
        # Handshake: machine sends its ID
        raw_hello = conn.recv(1024).decode("utf-8").strip()
        if not raw_hello:
            return
        # Handle string number or JSON
        if raw_hello.startswith("{"):
            data = json.loads(raw_hello)
            machine_id = int(data.get("machine_id", 1))
        else:
            machine_id = int(raw_hello.split()[0])

        with state_lock:
            tcp_connections[machine_id] = conn
            machines_state[machine_id]["connected_tcp"] = True
        print(f"[TCP Gateway] Machine {machine_id} connected from {addr}")

        while True:
            data = conn.recv(1024)
            if not data:
                break
            line = data.decode("utf-8").strip()
            # print(f"[TCP Gateway] Ack from machine {machine_id}: {line}")
            try:
                ack_payload = json.loads(line)
                with state_lock:
                    if "state" in ack_payload:
                        machines_state[machine_id]["state"] = ack_payload["state"]
                    if "speed" in ack_payload:
                        machines_state[machine_id]["motor_speed"] = ack_payload["speed"]
            except Exception:
                pass
    except Exception as err:
        print(f"[TCP Gateway] Connection error ({addr}): {err}")
    finally:
        if machine_id is not None:
            with state_lock:
                tcp_connections.pop(machine_id, None)
                if machine_id in machines_state:
                    machines_state[machine_id]["connected_tcp"] = False
        conn.close()
        print(f"[TCP Gateway] Machine {machine_id} disconnected")


def send_control_command(machine_id, command, value=None):
    """Dispatches command to a machine and updates local state optimistically."""
    cmd = command.upper()
    with state_lock:
        if machine_id in machines_state:
            if cmd == "START":
                machines_state[machine_id]["state"] = "RUNNING"
                machines_state[machine_id]["motor_state"] = "RUNNING"
                machines_state[machine_id]["valve_state"] = "OPEN"
                if machines_state[machine_id].get("motor_speed", 0) <= 0:
                    machines_state[machine_id]["motor_speed"] = 1500
            elif cmd == "STOP":
                machines_state[machine_id]["state"] = "STOPPED"
                machines_state[machine_id]["motor_state"] = "STOPPED"
                machines_state[machine_id]["motor_speed"] = 0
                machines_state[machine_id]["valve_state"] = "CLOSED"
            elif cmd == "RESET":
                machines_state[machine_id]["state"] = "STOPPED"
                machines_state[machine_id]["motor_state"] = "STOPPED"
                machines_state[machine_id]["motor_speed"] = 0
                machines_state[machine_id]["valve_state"] = "CLOSED"
                machines_state[machine_id]["alerts"] = []
            elif cmd == "SET_SPEED":
                try:
                    spd = int(value) if value is not None else 1500
                    machines_state[machine_id]["motor_speed"] = max(0, min(2400, spd))
                    if spd > 0:
                        machines_state[machine_id]["state"] = "RUNNING"
                        machines_state[machine_id]["motor_state"] = "RUNNING"
                        machines_state[machine_id]["valve_state"] = "OPEN"
                    else:
                        machines_state[machine_id]["state"] = "STOPPED"
                        machines_state[machine_id]["motor_state"] = "STOPPED"
                        machines_state[machine_id]["valve_state"] = "CLOSED"
                except Exception:
                    pass
        conn = tcp_connections.get(machine_id)

    if conn is not None:
        try:
            msg = json.dumps({"command": cmd, "value": value}) + "\n"
            conn.sendall(msg.encode("utf-8"))
            print(f"[TCP Gateway] Sent {cmd} (val={value}) to machine {machine_id}")
        except Exception as err:
            print(f"[TCP Gateway] Send error: {err}")
    else:
        print(f"[TCP Gateway] Machine {machine_id} command {cmd} applied locally")
    return True


def run_tcp_server():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((TCP_HOST, TCP_PORT))
    server.listen(NUM_MACHINES + 2)
    print(f"[TCP Gateway] Control server listening on port {TCP_PORT}")
    while True:
        conn, addr = server.accept()
        threading.Thread(target=handle_tcp_machine, args=(conn, addr), daemon=True).start()


# ==========================================
# 3) UDP Server -> Emergency / Fault Alerts
# ==========================================
def run_udp_server():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((UDP_HOST, UDP_PORT))
    print(f"[UDP Gateway] Alert server listening on port {UDP_PORT}")
    while True:
        data, addr = sock.recvfrom(2048)
        try:
            payload = json.loads(data.decode("utf-8"))
            machine_id = int(payload.get("machine_id", 1))
            alert_type = payload.get("alert", "UNKNOWN_FAULT")
            timestamp = payload.get("timestamp", time.time())

            alert_entry = {
                "machine_id": machine_id,
                "alert": alert_type,
                "timestamp": timestamp,
                "time_str": time.strftime("%H:%M:%S", time.localtime(timestamp)),
            }

            with state_lock:
                if machine_id in machines_state:
                    machines_state[machine_id]["alerts"].append(alert_entry)
                    # Keep latest 10 alerts per machine
                    machines_state[machine_id]["alerts"] = machines_state[machine_id]["alerts"][-10:]
                recent_alerts.append(alert_entry)
                # Keep latest 25 alerts globally
                if len(recent_alerts) > 25:
                    recent_alerts.pop(0)

            print(f"[UDP Gateway] ALERT from Machine {machine_id}: {alert_type}")
        except Exception as err:
            print(f"[UDP Gateway] Packet parse error from {addr}: {err}")


# ==========================================
# 4) Blynk IoT Cloud REST Integration
# ==========================================
def blynk_http_get(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "SIC-Gateway/1.0"})
        with urllib.request.urlopen(req, timeout=3.0) as res:
            return res.read().decode("utf-8").strip()
    except Exception:
        return None


def run_blynk_sync_worker():
    global last_blynk_v4_val
    print("[Blynk Gateway] REST synchronization worker started.")

    while True:
        time.sleep(0.5)
        try:
            with state_lock:
                mid = blynk_active_machine
                machine = dict(machines_state.get(mid, {}))

            if not machine:
                continue

            temp = machine.get("temperature", 25.0)
            vib = machine.get("vibration", 0.0)
            prox = machine.get("proximity", 0)
            speed = machine.get("motor_speed", 0)
            m_state = machine.get("state", "STOPPED")

            # 1. Update Telemetry: V0, V1, V2, V3 using batch/update
            params = urllib.parse.urlencode({
                "token": BLYNK_AUTH_TOKEN,
                VPIN_TEMPERATURE: f"{temp:.1f}",
                VPIN_VIBRATION: f"{vib:.1f}",
                VPIN_PROXIMITY: str(prox),
                VPIN_MOTOR_SPEED: str(int(speed)),
            })
            update_url = f"{BLYNK_BASE_URL}/batch/update?{params}"
            blynk_http_get(update_url)

            # 2. Poll V4 (Start/Stop Command from Blynk Dashboard)
            v4_query_url = f"{BLYNK_BASE_URL}/get?token={BLYNK_AUTH_TOKEN}&{VPIN_START_STOP}"
            v4_val = blynk_http_get(v4_query_url)

            if v4_val is not None and v4_val in ["0", "1"]:
                if last_blynk_v4_val is None:
                    # Initial synchronization: record current cloud state
                    last_blynk_v4_val = v4_val
                elif v4_val != last_blynk_v4_val:
                    print(f"[Blynk Gateway] V4 button changed to {v4_val} on Blynk App!")
                    last_blynk_v4_val = v4_val
                    cmd = "START" if v4_val == "1" else "STOP"
                    send_control_command(mid, cmd)
                else:
                    # Cloud hasn't changed; if local state changed, update cloud
                    expected_v4 = "1" if m_state == "RUNNING" else "0"
                    if last_blynk_v4_val != expected_v4:
                        sync_v4_url = f"{BLYNK_BASE_URL}/update?token={BLYNK_AUTH_TOKEN}&{VPIN_START_STOP}={expected_v4}"
                        blynk_http_get(sync_v4_url)
                        last_blynk_v4_val = expected_v4

        except Exception as err:
            pass


# ==========================================
# 5) Flask Web Server & CORS REST API
# ==========================================
app = Flask(__name__, static_folder="public", template_folder="public")


@app.after_request
def add_cors_headers(response):
    """Enables CORS for production frontend (https://iotnexa-sic.web.app) and local access."""
    origin = request.headers.get("Origin")
    response.headers["Access-Control-Allow-Origin"] = origin if origin else "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-Requested-With, Access-Control-Request-Private-Network"
    response.headers["Access-Control-Allow-Credentials"] = "true"
    response.headers["Access-Control-Allow-Private-Network"] = "true"
    return response


@app.route("/", defaults={"path": ""})
@app.route("/<path:path>", methods=["OPTIONS"])
def handle_options(path):
    response = app.make_response(("", 204))
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-Requested-With, Access-Control-Request-Private-Network"
    response.headers["Access-Control-Allow-Private-Network"] = "true"
    return response


@app.route("/")
def serve_index():
    return send_from_directory("public", "index.html")


@app.route("/<path:path>")
def serve_static(path):
    return send_from_directory("public", path)


@app.route("/api/status", methods=["GET"])
def api_status():
    """Returns real-time telemetry, actuator states, and alerts of all 5 machines."""
    with state_lock:
        data = {
            "success": True,
            "blynk_active_machine": blynk_active_machine,
            "machines": list(machines_state.values()),
            "alerts": recent_alerts[-15:],
            "timestamp": time.time(),
        }
    return jsonify(data)


@app.route("/api/machines", methods=["GET"])
def api_machines():
    """Alternative array format for backwards compatibility with older dashboard scripts."""
    with state_lock:
        res = []
        for m in machines_state.values():
            res.append({
                "id": m["id"],
                "state": m["state"],
                "temperature": round(m["temperature"], 1),
                "vibration": round(m["vibration"], 1),
                "speed": int(m["motor_speed"]),
                "proximity": m["proximity"],
                "valve_state": m["valve_state"],
            })
    return jsonify(res)


@app.route("/api/command", methods=["POST"])
def api_command_post():
    """Dispatches TCP command to a machine: {"machine_id": 1..5, "command": "START"|"STOP"|"RESET"|"SET_SPEED", "value": ...}"""
    body = request.get_json(silent=True) or {}
    machine_id = int(body.get("machine_id", 1))
    cmd = body.get("command", "").upper()
    val = body.get("value")

    if not cmd:
        return jsonify({"success": False, "error": "Missing command"}), 400

    success = send_control_command(machine_id, cmd, val)
    return jsonify({"success": success, "machine_id": machine_id, "command": cmd, "value": val})


@app.route("/api/command/<int:machine_id>/<command>", methods=["GET", "POST"])
def api_command_get(machine_id, command):
    val = request.args.get("value")
    success = send_control_command(machine_id, command.upper(), val)
    return jsonify({"success": success, "machine_id": machine_id, "command": command.upper(), "value": val})


@app.route("/api/blynk/select", methods=["POST"])
def api_blynk_select():
    global blynk_active_machine
    body = request.get_json(silent=True) or {}
    mid = int(body.get("machine_id", 1))
    if 1 <= mid <= NUM_MACHINES:
        with state_lock:
            blynk_active_machine = mid
        return jsonify({"success": True, "blynk_active_machine": mid})
    return jsonify({"success": False, "error": "Invalid machine_id"}), 400


@app.route("/api/blynk/status", methods=["GET"])
def api_blynk_status():
    return jsonify({
        "success": True,
        "token": BLYNK_AUTH_TOKEN[:6] + "..." + BLYNK_AUTH_TOKEN[-4:],
        "active_machine": blynk_active_machine,
        "pins": {
            "V0": "Temperature",
            "V1": "Vibration",
            "V2": "Proximity",
            "V3": "Motor Speed",
            "V4": "StartandStop",
        },
    })


@app.route("/api/simulate/fault", methods=["POST"])
def api_simulate_fault():
    """Injects a test fault: {"machine_id": 1, "fault": "TEMP_HIGH" | "VIB_HIGH" | "SENSOR_FAULT"}"""
    body = request.get_json(silent=True) or {}
    machine_id = int(body.get("machine_id", 1))
    fault = body.get("fault", "SENSOR_FAULT").upper()

    success = send_control_command(machine_id, "TRIGGER_FAULT", fault)
    return jsonify({"success": success, "machine_id": machine_id, "fault": fault})


def run_http_server():
    print(f"[HTTP Gateway] Serving Web Dashboard and REST API on http://{HTTP_HOST}:{HTTP_PORT}")
    app.run(host=HTTP_HOST, port=HTTP_PORT, debug=False, use_reloader=False)


# ==========================================
# 6) Main Execution
# ==========================================
if __name__ == "__main__":
    print("=" * 65)
    print("Starting SIC Industrial IoT Gateway (Raspberry Pi Software Edition)")
    print("=" * 65)

    threading.Thread(target=run_mqtt_client, daemon=True).start()
    threading.Thread(target=run_tcp_server, daemon=True).start()
    threading.Thread(target=run_udp_server, daemon=True).start()
    threading.Thread(target=run_blynk_sync_worker, daemon=True).start()

    run_http_server()