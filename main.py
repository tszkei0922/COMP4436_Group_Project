import network
import time
from machine import Pin, ADC, I2C
import dht
import urequests
from umqtt.simple import MQTTClient
import json
import random
import ubinascii
import machine

# WiFi Configuration
SSID = "Thunderstorm3"
PASSWORD = "98705058"

# Sensors
dht11 = dht.DHT11(Pin(4))
ldr = ADC(Pin(34))
ldr.atten(ADC.ATTN_11DB)
led = Pin(2, Pin.OUT)  # LED pin for status indication

# InfluxDB Configuration
INFLUXDB_URL = "https://us-east-1-1.aws.cloud2.influxdata.com"
# INFLUXDB_TOKEN = "k1YKqkvun2CVGuaDCFSzodwsiSoFdHkUsE7_rWBSzf0ubtsq7GYwKPycBbixT5vlt4mVCpxqDXeAe2Z5BYQzvQ=="
INFLUXDB_TOKEN = "QDDpmXr8jhPNEg4F5qV-pJVHs6GxGWgXcQHMmbdjNESY06ohnrNyTngVRS5aFZ8wp0b-3HGHi6pEtbLv-kIdjw==" #new
INFLUXDB_ORG = "5023c10e3657904b"
#INFLUXDB_BUCKET = "COMP4436"
INFLUXDB_BUCKET = "COMP4436-2"
INFLUXDB_URL_WRITE = f"{INFLUXDB_URL}/api/v2/write?org={INFLUXDB_ORG}&bucket={INFLUXDB_BUCKET}&precision=s"

# MQTT Configuration
MQTT_BROKER = "broker.hivemq.com"  # Free public MQTT broker
MQTT_PORT = 1883
MQTT_CLIENT_ID = "esp32_sensor"
MQTT_TOPIC_SEND = "esp32/sensor_data"
MQTT_TOPIC_RECEIVE = "esp32/predicted_light"

# Mode Configuration
LEARNING_MODE = True  # Set to False for smart mode

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
    # Generate a unique client ID using the ESP32's unique ID
    client_id = f"{MQTT_CLIENT_ID}_{ubinascii.hexlify(machine.unique_id()).decode()}"
    
    try:
        client = MQTTClient(client_id, MQTT_BROKER, MQTT_PORT, keepalive=30)
        client.set_callback(on_mqtt_message)
        client.connect()
        client.subscribe(MQTT_TOPIC_RECEIVE)
        print(f"Connected to MQTT broker with ID: {client_id}")
        return client
    except Exception as e:
        print(f"MQTT connection failed: {str(e)}")
        return None

def on_mqtt_message(topic, msg):
    if topic.decode() == MQTT_TOPIC_RECEIVE:
        predicted_light = int (msg.decode())
        print(f"Received predicted light value: {predicted_light}")
        if predicted_light == 0:
            led.value(1)  # Turn on LED
            print("LED ON")
        else:
            led.value(0)  # Turn off LED
            print("LED OFF")
        # You can add code here to handle the predicted value
        # For example, store it or use it for control logic

def read_dht11():
    try:
        dht11.measure()
        temp = dht11.temperature()
        hum = dht11.humidity()
        print(f"Temperature: {temp} Celsius, Humidity: {hum}%")
        return temp, hum
    except OSError as e:
        print("DHT11 read error:", e)
        return None, None
    
def read_ldr():
    try:
        ldr_value = ldr.read()
        light_binary = 1 if ldr_value > 2047 else 0
        print(f"Light Value: {ldr_value} (Binary: {light_binary})")
        return light_binary
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
    while True:
        led.value(0)
        temp, hum = read_dht11()
        ldr_value = read_ldr()
        send_to_influxdb(temp, hum, ldr_value)
        time.sleep(60)

def smart_mode_loop(mqtt_client):
    while True:
        if mqtt_client is None:
            print("Attempting to connect to MQTT...")
            mqtt_client = connect_mqtt()
            if mqtt_client is None:
                print("Failed to connect to MQTT. Retrying in 30 seconds...")
                time.sleep(5)
                continue
                
        try:
            temp, hum = read_dht11()
            if temp is not None and hum is not None:
                data = json.dumps({
                    "temperature": temp,
                    "humidity": hum
                })
                mqtt_client.publish(MQTT_TOPIC_SEND, data)
                print(f"Sent sensor data: Temp={temp}°C, Humidity={hum}%")
                
                # Check for messages with timeout
                mqtt_client.wait_msg()
                
        except Exception as e:
            print(f"Error in smart mode loop: {str(e)}")
            try:
                mqtt_client.disconnect()
            except:
                pass
            mqtt_client = None
            time.sleep(5)
        
        time.sleep(5)  # Reduced sleep time for more frequent updates

def main():
    if connect_wifi(SSID, PASSWORD):
        mqtt_client = connect_mqtt()
        if LEARNING_MODE:
            print("Running in Learning Mode")
            learning_mode_loop(mqtt_client)
             # Turn on LED to indicate learning mode
        else:
            print("Running in Smart Mode")
            smart_mode_loop(mqtt_client)
    else:
        print("WiFi connection failed, exiting...")

if __name__ == "__main__":
    main()