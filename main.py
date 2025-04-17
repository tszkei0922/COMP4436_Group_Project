import network
import time
from machine import Pin, ADC, I2C
import dht
import urequests
from umqtt.simple import MQTTClient
import json

# WiFi Configuration
SSID = "Thunderstorm3"
PASSWORD = "98705058"

# Sensors
dht11 = dht.DHT11(Pin(4))
ldr = ADC(Pin(34))
ldr.atten(ADC.ATTN_11DB)

# InfluxDB Configuration
INFLUXDB_URL = "https://us-east-1-1.aws.cloud2.influxdata.com"
INFLUXDB_TOKEN = "k1YKqkvun2CVGuaDCFSzodwsiSoFdHkUsE7_rWBSzf0ubtsq7GYwKPycBbixT5vlt4mVCpxqDXeAe2Z5BYQzvQ=="
INFLUXDB_ORG = "5023c10e3657904b"
INFLUXDB_BUCKET = "COMP4436"
INFLUXDB_URL_WRITE = f"{INFLUXDB_URL}/api/v2/write?org={INFLUXDB_ORG}&bucket={INFLUXDB_BUCKET}&precision=s"

# MQTT Configuration
MQTT_BROKER = "broker.hivemq.com"  # Free public MQTT broker
MQTT_PORT = 1883
MQTT_CLIENT_ID = "esp32_sensor"
MQTT_TOPIC_SEND = "esp32/sensor_data"
MQTT_TOPIC_RECEIVE = "esp32/predicted_light"

# Mode Configuration
LEARNING_MODE = False  # Set to True for learning mode, False for smart mode

# Light Control
LIGHT_PIN = Pin(2, Pin.OUT)  # Assuming GPIO 2 controls the light

def connect_wifi(ssid, password):
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        print(f"Connecting to {ssid}...")
        wlan.connect(ssid, password)
        timeout = 15
        start = time.time()
        while not wlan.isconnected():
            if time.time() - start > timeout:
                print("Failed to Connect to WiFi")
                return False
            time.sleep(0.5)
            print("Wifi Status:", wlan.status())
    print("Successfully connected! IP address:", wlan.ifconfig()[0])
    return True

def connect_mqtt():
    client = MQTTClient(MQTT_CLIENT_ID, MQTT_BROKER, MQTT_PORT)
    client.set_callback(on_mqtt_message)
    client.connect()
    client.subscribe(MQTT_TOPIC_RECEIVE)
    print("Connected to MQTT broker")
    return client

def on_mqtt_message(topic, msg):
    """Handle incoming MQTT messages with binary light predictions"""
    try:
        # First check if we received the correct topic
        if topic.decode() != MQTT_TOPIC_RECEIVE:
            return
            
        # Safely decode the message
        try:
            msg_str = msg.decode()
        except Exception as e:
            print("Error decoding message:", e)
            return
            
        # Convert to integer and validate
        try:
            predicted_light = int(msg_str)
        except ValueError:
            print("Error: Message is not a valid integer")
            return
            
        # Validate the prediction value
        if predicted_light not in [0, 1]:
            print("Error: Invalid prediction value:", predicted_light)
            return
            
        # Control the light based on prediction
        try:
            LIGHT_PIN.value(predicted_light)
            light_status = "ON" if predicted_light == 1 else "OFF"
            print(f"Light set to {light_status}")
        except Exception as e:
            print("Error controlling light:", e)
            
    except Exception as e:
        print("Error in message handler:", e)
        # Don't re-raise the exception to prevent MQTT client from crashing

def read_dht11():
    try:
        dht11.measure()
        temp = dht11.temperature()
        hum = dht11.humidity()
        print(f"Temperature: {temp}°C, Humidity: {hum}%")
        return temp, hum
    except OSError as e:
        print("DHT11 read error:", e)
        return None, None
    
def read_ldr():
    try:
        ldr_value = ldr.read()
        light_percent = (ldr_value / 4095) * 100
        print(f"Light Value: {ldr_value} (Around {light_percent:.1f}%)")
        return ldr_value
    except Exception as e:
        print("LDR Error:", e)
        return None

def send_to_influxdb(temp, hum, ldr_value):
    if temp is None or hum is None or ldr_value is None:
        print("Error data, not sending to InfluxDB")
        return
    data = (
        f"sensor_data,device=ESP32 "
        f"temperature={temp},humidity={hum},light={ldr_value}"
    )
    headers = {
        "Authorization": f"Token {INFLUXDB_TOKEN}",
        "Content-Type": "text/plain; charset=utf-8"
    }
    try:
        print(f"Sending data: {data}")
        response = urequests.post(INFLUXDB_URL_WRITE, headers=headers, data=data)
        print(f"InfluxDB response: {response.status_code} {response.reason}")
        response.close()
    except Exception as e:
        print("InfluxDB Error:", e)

def learning_mode_loop(mqtt_client):
    """Collect sensor data and send to InfluxDB for model training"""
    while True:
        temp, hum = read_dht11()
        ldr_value = read_ldr()
        send_to_influxdb(temp, hum, ldr_value)
        time.sleep(60)

def smart_mode_loop(mqtt_client):
    """Use ML model to control light based on sensor data"""
    while True:
        temp, hum = read_dht11()
        if temp is not None and hum is not None:
            # Send sensor data to model.py via MQTT
            data = json.dumps({
                "temperature": temp,
                "humidity": hum
            })
            mqtt_client.publish(MQTT_TOPIC_SEND, data)
            print(f"Sent sensor data for prediction: Temp={temp}°C, Humidity={hum}%")
            
            # Check for incoming messages (predictions)
            mqtt_client.wait_msg()
        
        time.sleep(60)

def main():
    # Initialize light to OFF
    LIGHT_PIN.value(0)
    
    if connect_wifi(SSID, PASSWORD):
        mqtt_client = connect_mqtt()
        
        if LEARNING_MODE:
            print("Running in Learning Mode")
            print("Collecting sensor data for model training...")
            learning_mode_loop(mqtt_client)
        else:
            print("Running in Smart Mode")
            print("Using ML model to control light...")
            smart_mode_loop(mqtt_client)
    else:
        print("WiFi connection failed, exiting...")

if __name__ == "__main__":
    main()