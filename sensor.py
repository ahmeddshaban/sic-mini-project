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

def on_connect(client, userdata, flags):
    print(f"Machine Connected to MQTT Broker.")
    
    client.subscribe(COMMAND_TOPIC)

def on_message(client, userdata, msg):
    try:
        command = json.loads(msg.payload.decode('utf-8'))
        name = command.get("device")
        action = command.get("action")
        
        if name in actuator_states:
            actuator_states[name] = action
            print(f"Executing Command : {name}: {action}")
    except Exception:
        print(f"Machine error")

client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message
client.connect(BROKER, PORT, 60)
client.loop_start()  

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