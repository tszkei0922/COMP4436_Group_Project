# ESP32 MicroPython Sensor and InfluxDB Integration Project

## Project Overview
This project uses an ESP32 development board running MicroPython to achieve the following:
- Read temperature and humidity data from a **DHT11** sensor.
- Read light intensity data from a **Light-Dependent Resistor (LDR)**.
- Connect to WiFi network.
- Send sensor data to **InfluxDB** (Cloud or local) for storage.
- Develop and deploy code using **VS Code** with the **Pymakr** extension.

The project is ideal for IoT applications like environmental monitoring and demonstrates integrating an ESP32 with a cloud database.

## Hardware Requirements
- **ESP32 Development Board** (e.g., DevKitC, serial port: `/dev/cu.usbserial-A5069RR4`)
- **DHT11 Sensor** (temperature and humidity)
- **Light-Dependent Resistor (LDR)** (light intensity)
- **10kΩ Resistor** (for LDR voltage divider circuit)
- **Jumper Wires** (for sensor connections)
- **USB Data Cable** (to connect ESP32 to Mac)

## Software Requirements
- **MicroPython Firmware** (latest stable version, e.g., v1.20.0)
- **VS Code** (with Pymakr extension)
- **Python 3** (for flashing firmware and querying InfluxDB locally)
- **esptool.py** (for flashing MicroPython)
- **InfluxDB**:
  - InfluxDB Cloud (free tier)
  - Configured bucket (e.g., `"COMP4436"`) and API Token

## Hardware Wiring
### DHT11 Wiring
| DHT11 Pin | ESP32 Pin | Description |
|-----------|-----------|-------------|
| VCC       | 3.3V      | Power       |
| DATA      | GPIO 4    | Data (requires 4.7kΩ or 10kΩ pull-up resistor) |
| GND       | GND       | Ground      |

### LDR Wiring
| LDR/Resistor | ESP32 Pin | Description |
|--------------|-----------|-------------|
| LDR One End  | GPIO 34   | ADC Input   |
| LDR Other End | GND       | Ground      |
| 10kΩ Resistor | GPIO 34 - 3.3V | Voltage Divider |

## Installation and Setup

### 1. Install MicroPython
1. Download the latest MicroPython firmware (https://micropython.org/download/esp32/).
2. Erase the ESP32 flash memory:
   ```bash
   esptool.py --port /dev/cu.usbserial-A5069RR4 erase_flash
   ```
3. Flash the firmware (assuming firmware is at `~/Downloads/esp32-micropython.bin`):
   ```bash
   esptool.py --chip esp32 --port /dev/cu.usbserial-A5069RR4 --baud 460800 write_flash -z 0x1000 ~/Downloads/esp32-micropython.bin
   ```

### 2. Set Up VS Code and Pymakr
1. Install VS Code (https://code.visualstudio.com).
2. Install the Pymakr extension (search `Pymakr` in VS Code Extensions panel).
3. Create a project folder (e.g., `~/ESP32_MicroPython`).
4. Configure `pymakr.json`:
   ```json
   {
     "address": "/dev/cu.usbserial-A5069RR4",
     "safe_boot_on_upload": false,
     "sync_folder": "",
     "auto_connect": true
   }
   ```

### 3. Set Up InfluxDB
1. **InfluxDB Cloud**:
   - Sign up and log in at https://cloud2.influxdata.com.
   - Create a bucket (e.g., `"esp32_sensors"`).
   - Obtain the following (from “Load Data > API Tokens”):
     - URL (e.g., `https://us-east-1-1.aws.cloud2.influxdata.com`)
     - API Token
     - Organization ID
     - Bucket Name
2. **Local InfluxDB**:
   - Install:
     ```bash
     brew install influxdb
     influxd
     ```
   - Open http://localhost:8086, create a bucket and token.

### 4. Configure Code
The core code is in `main.py`, which reads sensor data and sends it to InfluxDB. Copy the following to `~/ESP32_MicroPython/main.py`:

### 5. Deploy Code
1. Hard reset the ESP32:
   - Press the **EN** or **RESET** button on the board, or unplug/replug the USB cable (wait 5 seconds).
2. Open VS Code and navigate to `~/ESP32_MicroPython`.
3. In the Pymakr console, click “Sync project to device”.
4. Check the output, which should look like:
   ```
   Connecting to Thunderstorm3...
   Connected! IP address: 192.168.x.x
   Temperature: 25°C, Humidity: 60%
   Light intensity: 2000 (~48.8%)
   Sending data: sensor_data,device=ESP32 temperature=25.0,humidity=60.0,light=2000.0
   InfluxDB response: 204 OK
   ```