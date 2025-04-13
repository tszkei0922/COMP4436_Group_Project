import network
import time
from machine import Pin, ADC, I2C
import dht
import urequests

SSID = "Thunderstorm3"
PASSWORD = "98705058"
dht11 = dht.DHT11(Pin(4))

ldr = ADC(Pin(34))
ldr.atten(ADC.ATTN_11DB)

# InfluxDB
INFLUXDB_URL = "https://us-east-1-1.aws.cloud2.influxdata.com"
INFLUXDB_TOKEN = "k1YKqkvun2CVGuaDCFSzodwsiSoFdHkUsE7_rWBSzf0ubtsq7GYwKPycBbixT5vlt4mVCpxqDXeAe2Z5BYQzvQ=="
INFLUXDB_ORG = "5023c10e3657904b"
INFLUXDB_BUCKET = "COMP4436"
INFLUXDB_URL_WRITE = f"{INFLUXDB_URL}/api/v2/write?org={INFLUXDB_ORG}&bucket={INFLUXDB_BUCKET}&precision=s"

def connect_wifi(ssid, password):
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        print(f"Connenting to {ssid}...")
        wlan.connect(ssid, password)
        timeout = 15  # 秒
        start = time.time()
        while not wlan.isconnected():
            if time.time() - start > timeout:
                print("Fail to Connect to WiFi")
                return False
            time.sleep(0.5)
            print("Wifi Status:", wlan.status())
    print("Successful! IP address:", wlan.ifconfig()[0])
    return True

# DHT11 溫濕度感測器初始化
def read_dht11():
    try:
        dht11.measure()  # 觸發測量
        temp = dht11.temperature()  # 溫度（攝氏）
        hum = dht11.humidity()      # 濕度（%）
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
        print(f"發送數據: {data}")
        response = urequests.post(INFLUXDB_URL_WRITE, headers=headers, data=data)
        print(f"InfluxDB response: {response.status_code} {response.reason}")
        print("InfluxDB response text:", response.text)
        response.close()
    except Exception as e:
        print("InfluxDB Error:", e)



# 主迴圈
def main():
    if connect_wifi(SSID, PASSWORD):
        while True:
            temp, hum = read_dht11()
            ldr_value = read_ldr()
            send_to_influxdb(temp, hum, ldr_value)
            time.sleep(60)  # DHT11 建議每 2 秒讀取一次
    else:
        print("Wifi connection failed, exiting...")

main()