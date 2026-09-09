import json
import paho.mqtt.client as mqtt

BROKER = "broker.hivemq.com"
PORT = 1883
Sensor_TOPIC = "factory/sensors/data"
COMMAND_TOPIC = "factory/actuators/control"

def on_connect(client, userdata, flags, reason_code=None, properties=None):
    print("Server Connected to broker.")
    client.subscribe(Sensor_TOPIC)

def send_control_command(client, device, action):
    cmd_payload = json.dumps({"device": device, "action": action})
    client.publish(COMMAND_TOPIC, cmd_payload)
    print(f"Published Control Command: ({cmd_payload})")

def on_message(client, userdata, msg):
    try:
        payload_str = msg.payload.decode('utf-8')
        sensors_list = json.loads(payload_str)
        
        if isinstance(sensors_list, dict):
            sensors_list = [sensors_list]
        elif not isinstance(sensors_list, list):
            return

        for sensor in sensors_list:
            name = sensor.get("name")
            value = sensor.get("value")
            
            # High Vibration : Stop conveyor and close valve
            if name == "vibration" and value > 70:
                print(f"High vibration :({value})!")
                send_control_command(client, "Conveyor", "OFF")
                send_control_command(client, "Valve", "CLOSED")
            
            # Normal Vibration : Keep conveyor running
            elif name == "vibration" and value <= 30:
                send_control_command(client, "Conveyor", "ON")
                send_control_command(client, "Valve", "OPEN")

    except Exception as e:
        print(f"Server error: {e}")

try:
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
except AttributeError:
    client = mqtt.Client()

client.on_connect = on_connect
client.on_message = on_message

client.connect(BROKER, PORT, 60)

try:
    client.loop_forever()
except KeyboardInterrupt:
    print("\nStopping server...")
    client.disconnect()