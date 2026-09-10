#Karim Added Udp & TCP Listener to receive commands from server.py and update actuator states accordingly
import socket
import threading
import json
import time
import random
import paho.mqtt.client as mqtt

TCP_IP = '127.0.0.1'
TCP_PORT = 5000
UDP_IP = '127.0.0.1'
UDP_PORT = 5001
BROKER = "broker.hivemq.com"
MQTT_PORT = 1883
SENSOR_TOPIC = "factory/sensors/data"

machine_state = {
    "status": "STOPPED",
    "speed": 0
}

def tcp_control_server():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) # Karim Added Tcp And Udp
    server.bind((TCP_IP, TCP_PORT))
    server.listen(5)
    
    while True:
        conn, addr = server.accept()
        data = conn.recv(1024).decode('utf-8')
        
        if data:
            command = json.loads(data)
            cmd_type = command.get("command")
            
            if cmd_type == "START":
                machine_state["status"] = "RUNNING"
            elif cmd_type == "STOP":
                machine_state["status"] = "STOPPED"
            elif cmd_type == "RESET":
                machine_state["status"] = "STOPPED"
                machine_state["speed"] = 0
            elif cmd_type == "SET_SPEED":
                machine_state["speed"] = command.get("value", 0)
                
            print(f"State Updated via TCP: {machine_state}")
            conn.send(json.dumps(machine_state).encode('utf-8'))
            
        conn.close()
    
    while True:
        conn, addr = server.accept()
        data = conn.recv(1024).decode('utf-8')
        
        if data:
            command = json.loads(data)
            cmd_type = command.get("command")
            
            if cmd_type == "START":
                machine_state["status"] = "RUNNING"
            elif cmd_type == "STOP":
                machine_state["status"] = "STOPPED"
            elif cmd_type == "RESET":
                machine_state["status"] = "STOPPED"
                machine_state["speed"] = 0
            elif cmd_type == "SET_SPEED":
                machine_state["speed"] = command.get("value", 0)
                
            print(f"State Updated via TCP: {machine_state}")
            conn.send(json.dumps(machine_state).encode('utf-8'))
            
        conn.close()

def udp_alert_sender():
    udp_client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    
    while True:
        temp = random.randint(20, 95)
        vib = random.randint(10, 95)
        
        alert_msg = None
        if temp > 85:
            alert_msg = "TEMP_HIGH"
        elif vib > 85:
            alert_msg = "VIB_HIGH"
            
        if alert_msg:
            payload = json.dumps({"machine": 1, "alert": alert_msg})
            udp_client.sendto(payload.encode('utf-8'), (UDP_IP, UDP_PORT))
            print(f"UDP Alert Sent: {payload}")
            
        time.sleep(3)

threading.Thread(target=tcp_control_server, daemon=True).start()
threading.Thread(target=udp_alert_sender, daemon=True).start()

try:
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
except AttributeError:
    client = mqtt.Client()

client.connect(BROKER, MQTT_PORT, 60)
client.loop_start()

while True:
    data = [
        {"name": "temperature", "value": random.randint(15, 40)},
        {"name": "proximity", "value": random.randint(0, 1)},
        {"name": "vibration", "value": random.randint(0, 100)},
        {"name": "status", "value": machine_state["status"]},
        {"name": "speed", "value": machine_state["speed"]}
    ]
    payload = json.dumps(data)
    client.publish(SENSOR_TOPIC, payload)
    print(f"MQTT Data Sent: {payload}")
    time.sleep(2)