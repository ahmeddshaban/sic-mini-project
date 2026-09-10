import socket
import json
import time

commands = [
    {"device": "Conveyor", "action": "OFF"},
    {"device": "Valve", "action": "CLOSE"},
    {"device": "Conveyor", "action": "ON"},
    {"device": "Valve", "action": "OPEN"}
]

while True:
    for cmd in commands:
        try:
            tcp_client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            tcp_client.connect(('127.0.0.1', 5000))
            tcp_client.send(json.dumps(cmd).encode('utf-8'))
            tcp_client.close()
            print(f"Command Sent via TCP: {cmd}")
        except Exception as e:
            print("Waiting for connection...")
        
        time.sleep(5)