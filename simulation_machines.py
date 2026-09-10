"""
Samsung Innovation Campus (SIC8) - IoT Track
Multi-Machine Software Simulation Engine (Machines 1 -> 5)
Simulates sensors, actuators, and 3 communication protocols:
  1. MQTT -> Telemetry (Temperature, Vibration, Proximity, Motor State & Speed, Solenoid Valve)
  2. TCP  -> Bidirectional Command & Control (START/STOP, RESET, SET_SPEED)
  3. UDP  -> Emergency / Fault Alerts (TEMP_HIGH, VIB_HIGH, SENSOR_FAULT)
"""

import json
import random
import socket
import sys
import threading
import time
import paho.mqtt.client as mqtt

MQTT_BROKER = "broker.hivemq.com"
MQTT_PORT = 1883
TOPIC_BASE = "sic_factory/machine"

TCP_HOST = "127.0.0.1"
TCP_PORT = 6000

UDP_HOST = "127.0.0.1"
UDP_PORT = 7000

NUM_MACHINES = 5


class SimulatedMachine(threading.Thread):
    def __init__(self, machine_id, mqtt_client, udp_sock):
        super().__init__(daemon=True)
        self.machine_id = machine_id
        self.mqtt_client = mqtt_client
        self.udp_sock = udp_sock

        # State & Actuators
        self.state = "RUNNING" if machine_id <= 3 else "STOPPED"
        self.target_speed = 1500 if self.state == "RUNNING" else 0
        self.motor_speed = self.target_speed
        self.valve_state = "OPEN" if self.state == "RUNNING" else "CLOSED"

        # Sensors
        self.base_temp = 25.0 + (machine_id * 2.5)
        self.temperature = self.base_temp
        self.vibration = 18.0 + (machine_id * 3.0)
        self.proximity = 1

        # Faults & Alert Tracking
        self.fault = None
        self.last_alert_time = {}
        self.running = True

        # TCP Connection
        self.tcp_conn = None
        self.tcp_thread = None

    def trigger_alert(self, alert_type):
        now = time.time()
        # Cooldown per alert type: 5 seconds
        if now - self.last_alert_time.get(alert_type, 0) > 5.0:
            self.last_alert_time[alert_type] = now
            payload = json.dumps({
                "machine_id": self.machine_id,
                "alert": alert_type,
                "timestamp": now,
            }).encode("utf-8")
            try:
                self.udp_sock.sendto(payload, (UDP_HOST, UDP_PORT))
                print(f"[UDP Machine {self.machine_id}] Sent ALERT -> {alert_type}")
            except Exception as err:
                print(f"[UDP Machine {self.machine_id}] Error sending alert: {err}")

    def handle_tcp_command(self, cmd_data):
        cmd = cmd_data.get("command", "").upper()
        val = cmd_data.get("value")
        print(f"[TCP Machine {self.machine_id}] Received command: {cmd} (value={val})")

        if cmd == "START":
            self.state = "RUNNING"
            if self.target_speed == 0:
                self.target_speed = 1500
            self.motor_speed = self.target_speed
            self.valve_state = "OPEN"
            self.fault = None
        elif cmd == "STOP":
            self.state = "STOPPED"
            self.target_speed = 0
            self.motor_speed = 0
            self.valve_state = "CLOSED"
        elif cmd == "RESET":
            self.state = "STOPPED"
            self.target_speed = 0
            self.motor_speed = 0
            self.valve_state = "CLOSED"
            self.fault = None
            self.temperature = self.base_temp
            self.vibration = 20.0
        elif cmd == "SET_SPEED":
            try:
                new_speed = int(val) if val is not None else 1500
                self.target_speed = max(0, min(2400, new_speed))
                self.motor_speed = self.target_speed
                if self.target_speed > 0:
                    self.state = "RUNNING"
                    self.valve_state = "OPEN"
                else:
                    self.state = "STOPPED"
                    self.valve_state = "CLOSED"
            except (ValueError, TypeError):
                pass
        elif cmd == "TRIGGER_FAULT":
            fault_type = str(val).upper() if val else "SENSOR_FAULT"
            self.fault = fault_type
            if fault_type == "TEMP_HIGH":
                self.temperature = 92.5
            elif fault_type == "VIB_HIGH":
                self.vibration = 95.0
            self.trigger_alert(fault_type)

        # Publish immediate telemetry on command update
        try:
            telemetry = {
                "machine_id": self.machine_id,
                "temperature": round(self.temperature, 1),
                "vibration": round(self.vibration, 1),
                "proximity": self.proximity,
                "motor_state": self.state,
                "motor_speed": int(self.motor_speed),
                "valve_state": self.valve_state,
                "state": self.state,
                "fault": self.fault,
                "timestamp": time.time(),
            }
            self.mqtt_client.publish(f"{TOPIC_BASE}/{self.machine_id}/telemetry", json.dumps(telemetry))
        except Exception:
            pass

        ack = {
            "status": "ACK",
            "machine_id": self.machine_id,
            "state": self.state,
            "speed": self.motor_speed,
            "valve_state": self.valve_state,
        }
        return json.dumps(ack)

    def run_tcp_client(self):
        """Maintains persistent TCP connection to Gateway control server."""
        while self.running:
            try:
                conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                conn.connect((TCP_HOST, TCP_PORT))
                self.tcp_conn = conn
                # Send machine ID handshake
                conn.sendall(f"{self.machine_id}\n".encode("utf-8"))
                print(f"[TCP Machine {self.machine_id}] Connected to Gateway on port {TCP_PORT}")

                buffer = ""
                while self.running:
                    data = conn.recv(1024)
                    if not data:
                        break
                    buffer += data.decode("utf-8")
                    while "\n" in buffer or "}" in buffer:
                        try:
                            if "}" in buffer:
                                end_idx = buffer.find("}") + 1
                                raw_msg = buffer[:end_idx].strip()
                                buffer = buffer[end_idx:]
                            else:
                                raw_msg, buffer = buffer.split("\n", 1)
                                raw_msg = raw_msg.strip()

                            if not raw_msg:
                                continue
                            cmd_data = json.loads(raw_msg)
                            reply = self.handle_tcp_command(cmd_data)
                            conn.sendall((reply + "\n").encode("utf-8"))
                        except json.JSONDecodeError:
                            break
            except Exception:
                pass
            finally:
                if self.tcp_conn:
                    try:
                        self.tcp_conn.close()
                    except Exception:
                        pass
                    self.tcp_conn = None
                time.sleep(2)  # Reconnect backoff

    def run(self):
        # Start TCP client loop
        self.tcp_thread = threading.Thread(target=self.run_tcp_client, daemon=True)
        self.tcp_thread.start()

        cycle_counter = 0
        while self.running:
            time.sleep(1.0)
            cycle_counter += 1

            # 1. Update dynamic states
            if self.state == "RUNNING":
                # Smooth speed ramp towards target
                if self.motor_speed < self.target_speed:
                    self.motor_speed = min(self.target_speed, self.motor_speed + 150)
                elif self.motor_speed > self.target_speed:
                    self.motor_speed = max(self.target_speed, self.motor_speed - 150)

                # Valve toggles periodically while running
                if cycle_counter % 3 == 0:
                    self.valve_state = "OPEN" if self.valve_state == "CLOSED" else "OPEN"
                elif cycle_counter % 5 == 0:
                    self.valve_state = "CLOSED"

                # Temperature climbs with speed
                speed_ratio = (self.motor_speed / 2400.0)
                target_temp = self.base_temp + (speed_ratio * 15.0) + random.uniform(-0.5, 0.5)
                self.temperature += (target_temp - self.temperature) * 0.1

                # Vibration correlates with speed
                self.vibration = 10.0 + (speed_ratio * 35.0) + random.uniform(-1.5, 1.5)

                # Proximity sensor detects workpieces passing by
                self.proximity = 1 if (cycle_counter % 4 in [1, 2]) else 0
            else:
                # Stopped
                self.motor_speed = max(0, self.motor_speed - 250)
                self.valve_state = "CLOSED"
                self.temperature += (self.base_temp - self.temperature) * 0.05
                self.vibration = max(0.0, self.vibration * 0.7)
                self.proximity = 0

            # 2. Check for alerts / conditions
            if self.temperature > 85.0:
                self.trigger_alert("TEMP_HIGH")
            if self.vibration > 85.0:
                self.trigger_alert("VIB_HIGH")
            if self.fault == "SENSOR_FAULT":
                self.trigger_alert("SENSOR_FAULT")

            # 3. Publish MQTT Telemetry every 2 seconds
            if cycle_counter % 2 == 0:
                telemetry = {
                    "machine_id": self.machine_id,
                    "temperature": round(self.temperature, 1),
                    "vibration": round(self.vibration, 1),
                    "proximity": self.proximity,
                    "motor_state": self.state,
                    "motor_speed": int(self.motor_speed),
                    "valve_state": self.valve_state,
                    "state": self.state,
                    "fault": self.fault,
                    "timestamp": time.time(),
                }
                topic = f"{TOPIC_BASE}/{self.machine_id}/telemetry"
                try:
                    self.mqtt_client.publish(topic, json.dumps(telemetry))
                except Exception as err:
                    print(f"[MQTT Machine {self.machine_id}] Publish error: {err}")


def start_simulation():
    print("=" * 60)
    print("Starting SIC Industrial IoT Multi-Machine Simulation (1 -> 5)")
    print("Protocols: MQTT (Telemetry) | TCP (Control) | UDP (Alerts)")
    print("=" * 60)

    try:
        mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    except AttributeError:
        mqtt_client = mqtt.Client()

    mqtt_client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
    mqtt_client.loop_start()

    udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    machines = []
    for i in range(1, NUM_MACHINES + 1):
        m = SimulatedMachine(machine_id=i, mqtt_client=mqtt_client, udp_sock=udp_sock)
        m.start()
        machines.append(m)

    print(f"[Simulation] All {NUM_MACHINES} simulated machines are running.")
    return machines


if __name__ == "__main__":
    machines = start_simulation()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping simulation...")
        sys.exit(0)
