import json
import random
import time
import paho.mqtt.client as mqtt

BROKER = "broker.hivemq.com"
PORT = 1883
Sensor_TOPIC = "factory/sensors/data"
COMMAND_TOPIC = "factory/actuators/control"

actuator_states = {
    "Conveyor": "ON",
    "Valve": "OPEN"
}

def on_connect(client, userdata, flags, reason_code=None, properties=None):
    print("Machine Connected to MQTT Broker.")
    client.subscribe(COMMAND_TOPIC)

def on_message(client, userdata, msg):
    try:
        command = json.loads(msg.payload.decode('utf-8'))
        name = command.get("device")
        action = command.get("action")
        
        if name in actuator_states:
            actuator_states[name] = action
            print(f"Executing Command : {name}: {action}")
    except Exception as e:
        print(f"Machine error: {e}")

try:
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
except AttributeError:
    client = mqtt.Client()

client.on_connect = on_connect
client.on_message = on_message
client.connect(BROKER, PORT, 60)
client.loop_start()

try:
    while True:
        data = [
            {"name": "temperature", "value": random.randint(15, 40)},
            {"name": "proximity", "value": random.randint(0, 1)},
            {"name": "vibration", "value": random.randint(0, 100)},
        ]

        payload = json.dumps(data)
        client.publish(Sensor_TOPIC, payload)
        print(f"\nData sent: {payload}")
        print(f"Status:\n Conveyor: {actuator_states['Conveyor']} | Valve: {actuator_states['Valve']}")
        
        time.sleep(2)
except KeyboardInterrupt:
    print("\nStopping sensor simulation...")
    client.loop_stop()
    client.disconnect()