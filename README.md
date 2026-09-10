# Industrial IoT Smart Factory Monitoring System

## Project Overview
This repository contains the backend infrastructure and simulation environment for an Industrial IoT (IIoT) smart factory monitoring system. The project delivers a real-time telemetry pipeline, centralizing data from factory floor machines, processing actuator safety logic, and exposing the data to cloud dashboards for remote monitoring.

## System Architecture & Tech Stack
* **Core Backend:** Python (Threading, Socket, HTTP Server)
* **Messaging & Protocols:** MQTT v3.1.1 / v5.0, HTTP/REST, TCP/UDP
* **MQTT Client:** Paho MQTT v2
* **MQTT Broker:** `broker.hivemq.com` (Port: 1883)
* **Web Hosting:** Firebase Hosting (`https://iotnexa-sic.web.app`)
* **Cloud Integration:** Blynk IoT API Bridge

## Telemetry & Monitored Parameters
The system continuously tracks the state of 5 simulated industrial machines, publishing real-time data for:
* **Temperature:** Thermal monitoring for overheating prevention.
* **Vibration:** Structural and mechanical stability tracking.
* **Speed:** Motor RPM and operational pace.
* **Proximity:** Object and material detection status.

## Actuator Logic & Safety Control
Built-in safety constraints are implemented for Conveyor and Valve operations. The central gateway (`server.py`) parses incoming MQTT data and applies threshold logic. If critical parameters exceed safe limits (e.g., Vibration > 70), the system automatically triggers a `STOPPED` state, dropping the motor speed to `0` to prevent hardware failure.

## Project Structure
* `sensor.py`: The edge-node simulator. Generates realistic telemetry data, publishes payloads to the MQTT broker, and broadcasts high-priority UDP alerts for critical temperature or vibration spikes.
* `server.py`: The centralized IoT gateway. Subscribes to the MQTT broker to ingest sensor data, maintains an updated local state, exposes a CORS-enabled REST API, and pushes state updates to the Blynk Cloud via HTTP requests.
* **TCP Control Listener:** Embedded logic to accept external commands (`START`, `STOP`, `RESET`, `SET_SPEED`) and update actuator states accordingly.

## Execution Guide
To launch the factory simulation and gateway locally, execute the following commands in two separate terminal instances:

1. Initialize the centralized gateway and API server:
```bash
python server.py
Boot up the machine simulators to begin telemetry transmission:

Bash
python sensor.py
Engineering Team
Designed, developed, and deployed by the SIC Mini Project Team:

Ahmed Shaban Mohamed

Karim Khaled Ismail

Ahmed Ali

Safwat Mahmoud

© 2026 SIC Mini Project. All rights reserved.
