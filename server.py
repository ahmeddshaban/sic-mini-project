import json
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import paho.mqtt.client as mqtt

BROKER = "broker.hivemq.com"
PORT = 1883
Sensor_TOPIC = "factory/sensors/data"
COMMAND_TOPIC = "factory/actuators/control"

latest_machines_data = [
    {"id": i, "state": "RUNNING", "temperature": 25, "vibration": 30, "speed": 1500, "proximity": 15}
    for i in range(1, 6)
]

class CORSRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(latest_machines_data).encode('utf-8'))
    
    def log_message(self, format, *args):
        pass

def run_http_server():
    server = HTTPServer(('127.0.0.1', 5000), CORSRequestHandler)
    server.serve_forever()

def on_connect(client, userdata, flags, reason_code=None, properties=None):
    print("Server Connected to broker.")
    client.subscribe(Sensor_TOPIC)

def on_message(client, userdata, msg):
    global latest_machines_data
    try:
        payload_str = msg.payload.decode('utf-8')
        sensors_list = json.loads(payload_str)
        
        temp, vib, speed, status, prox = 25, 30, 1500, "RUNNING", 15
        
        for item in sensors_list:
            name = item.get("name")
            val = item.get("value")
            if name == "temperature": temp = val
            elif name == "vibration": vib = val
            elif name == "speed": speed = val
            elif name == "status": status = val
            elif name == "proximity": prox = val

        for i in range(5):
            latest_machines_data[i] = {
                "id": i + 1,
                "state": "STOPPED" if vib > 70 else "RUNNING",
                "temperature": temp + i,
                "vibration": vib + (i * 2),
                "speed": 0 if vib > 70 else (1500 + i * 50),
                "proximity": prox
            }
    except Exception as e:
        pass

try:
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
except AttributeError:
    client = mqtt.Client()

client.on_connect = on_connect
client.on_message = on_message
client.connect(BROKER, PORT, 60)

threading.Thread(target=run_http_server, daemon=True).start()

try:
    client.loop_forever()
except KeyboardInterrupt:
    print("\nStopping server...")
    client.disconnect()