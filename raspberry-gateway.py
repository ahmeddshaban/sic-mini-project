"""
 Samsung Innovation Campus (SIC8) - IoT Track - Mini Project - Support Session
"""
import json
import socket
import threading
import time
import paho.mqtt.client as mqtt
from flask import Flask, jsonify, render_template
import blynklib

NUM_MACHINES = 5
# MQTT => sensor telemetry + actuator feedback 
MQTT_BROKER = "localhost"          # Mosquitto broker 
MQTT_PORT = 1883
TOPIC_SENSORS = "factory/machine/+/sensors"        
TOPIC_ACTUATORS = "factory/machine/+/actuators"

# TCP  => control commands: START/STOP, RESET, SET_SPEED
TCP_HOST = "0.0.0.0"
TCP_PORT = 6000                     

# UDP  => fast alerts: TEMP_HIGH, VIB_HIGH, SENSOR_FAULT) 
UDP_HOST = "0.0.0.0"
UDP_PORT = 7000                    

HTTP_PORT = 8080

# Blynk vpins
BLYNK_AUTH_TOKEN = "T-fb4daKcYs7NpEU91Ur6-zt26uc-_P3"    #token key of bylnk
VPIN_TEMPERATURE = 0
VPIN_VIBRATION = 1
VPIN_PROXIMITY = 2
VPIN_MOTOR_SPEED = 3
VPIN_START_STOP_BUTTON = 4          

state_lock = threading.Lock()

machines_state = {
    i: {
        "proximity": None,
        "temperature": None,
        "vibration": None,
        "motor_state": None,
        "motor_speed": None,
        "valve_state": None,
        "alerts": [],
    }
    for i in range(1, NUM_MACHINES + 1)
}

tcp_connections = {}    # Keeps the live TCP connection of every machine 

# 3) MQTT  -->  sensor + actuator telemetry  (publish / subscribe)

def on_mqtt_connect(client, userdata, flags, rc):
    print(f"[MQTT] connected to broker (rc={rc})")
    client.subscribe(TOPIC_SENSORS)
    client.subscribe(TOPIC_ACTUATORS)

def on_mqtt_message(client, userdata, msg):
    """
    Expected topic shape:   factory/machine/<id>/sensors
    Expected payload (JSON): {"proximity": 1, "temperature": 42.5, "vibration": 0.03}
    """
    try:
        machine_id = int(msg.topic.split("/")[2])
        payload = json.loads(msg.payload.decode())
        with state_lock:
            machines_state[machine_id].update(payload)
        print(f"[MQTT] machine {machine_id} -> {payload}")
    except Exception as err:
        print(f"[MQTT] could not parse message: {err}")

def run_mqtt_client():
    client = mqtt.Client()
    client.on_connect = on_mqtt_connect
    client.on_message = on_mqtt_message
    client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
    client.loop_forever()   # blocking loop -> runs in its own thread

# 4) TCP  -->  control commands (START/STOP, RESET, SET_SPEED)
def handle_tcp_machine(conn, addr):
    machine_id = None
    try:
        hello = conn.recv(1024).decode().strip()
        machine_id = int(hello)
        with state_lock:
            tcp_connections[machine_id] = conn
        print(f"[TCP] machine {machine_id} connected from {addr}")

        while True:
            data = conn.recv(1024)
            if not data:
                break
            print(f"[TCP] ack from machine {machine_id}: {data.decode().strip()}")
    except Exception as err:
        print(f"[TCP] connection error ({addr}): {err}")
    finally:
        if machine_id is not None:
            with state_lock:
                tcp_connections.pop(machine_id, None)
        conn.close()
        print(f"[TCP] machine {machine_id} disconnected")


def send_control_command(machine_id, command, value=None):
    with state_lock:
        conn = tcp_connections.get(machine_id)
    if conn is None:
        print(f"[TCP] machine {machine_id} is not connected")
        return False
    try:
        conn.sendall(json.dumps({"command": command, "value": value}).encode())
        return True
    except Exception as err:
        print(f"[TCP] failed to send command: {err}")
        return False


def run_tcp_server():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((TCP_HOST, TCP_PORT))
    server.listen(NUM_MACHINES)
    print(f"[TCP] server listening on port {TCP_PORT}")
    while True:
        conn, addr = server.accept()
        threading.Thread(target=handle_tcp_machine, args=(conn, addr), daemon=True).start()

# 5) UDP  -->  fast fault / alert notifications

def run_udp_server():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((UDP_HOST, UDP_PORT))
    print(f"[UDP] server listening on port {UDP_PORT}")
    while True:
        data, addr = sock.recvfrom(1024)
        try:
            payload = json.loads(data.decode())
            machine_id = int(payload["machine_id"])
            alert = payload["alert"]           # "TEMP_HIGH" | "VIB_HIGH" | "SENSOR_FAULT"
            with state_lock:
                machines_state[machine_id]["alerts"].append(alert)
            print(f"[UDP] ALERT from machine {machine_id}: {alert}")
        except Exception as err:
            print(f"[UDP] bad packet from {addr}: {err}")

# 6) HTTP  -->  serves the Web Page dashboard + a small REST API
app = Flask(__name__)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/status")
def api_status():
    """Returns the current state of all machines as JSON."""
    with state_lock:
        return jsonify(machines_state)


@app.route("/api/command/<int:machine_id>/<command>")
def api_command(machine_id, command):
    """Example: /api/command/2/START  or  /api/command/2/RESET"""
    success = send_control_command(machine_id, command.upper())
    return jsonify({"success": success})

def run_http_server():
    app.run(host="0.0.0.0", port=HTTP_PORT)

# 7) BLYNK  -->  cloud dashboard

blynk = blynklib.Blynk(BLYNK_AUTH_TOKEN)


@blynk.handle_event(f"write V{VPIN_START_STOP_BUTTON}")
def on_blynk_button(pin, value):
    """Fires when the user taps the START/STOP button in the Blynk app."""
    command = "START" if value[0] == "1" else "STOP"
    send_control_command(machine_id=1, command=command)   # demo: controls machine 1

def run_blynk_client():
    last_push = 0
    while True:
        blynk.run()
        # push live data to the app roughly twice a second
        if time.time() - last_push > 0.5:
            with state_lock:
                m1 = machines_state[1]
            if m1["temperature"] is not None:
                blynk.virtual_write(VPIN_TEMPERATURE, m1["temperature"])
            if m1["vibration"] is not None:
                blynk.virtual_write(VPIN_VIBRATION, m1["vibration"])
            if m1["proximity"] is not None:
                blynk.virtual_write(VPIN_PROXIMITY, m1["proximity"])
            if m1["motor_speed"] is not None:
                blynk.virtual_write(VPIN_MOTOR_SPEED, m1["motor_speed"])
            last_push = time.time()
        time.sleep(0.05)


# 8) MAIN  -->  start every protocol handler in its own thread
if __name__ == "__main__":
    threading.Thread(target=run_mqtt_client, daemon=True).start()
    threading.Thread(target=run_tcp_server, daemon=True).start()
    threading.Thread(target=run_udp_server, daemon=True).start()
    threading.Thread(target=run_blynk_client, daemon=True).start()

    print("=== Gateway is up: MQTT + TCP + UDP + Blynk running, starting HTTP server ===")
    run_http_server()  