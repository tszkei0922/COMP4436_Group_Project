import paho.mqtt.client as mqtt
import json
import time
import random
import threading

# MQTT Configuration
MQTT_BROKER = "broker.hivemq.com"
MQTT_PORT = 1883
MQTT_CLIENT_ID = "test_client"
MQTT_TOPIC_RECEIVE = "esp32/sensor_data"
MQTT_TOPIC_SEND = "esp32/predicted_light"

# Test parameters
TEST_DURATION = 60  # seconds
SEND_INTERVAL = 5   # seconds

def on_connect(client, userdata, flags, rc):
    print(f"Connected to MQTT broker with result code {rc}")
    client.subscribe(MQTT_TOPIC_SEND)
    print(f"Subscribed to {MQTT_TOPIC_SEND}")

def on_message(client, userdata, msg):
    """Handle incoming MQTT messages with binary light predictions"""
    try:
        # First check if we received the correct topic
        if msg.topic != MQTT_TOPIC_SEND:
            return
            
        # Safely decode the message
        try:
            msg_str = msg.payload.decode()
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
            
        # Print the prediction result
        light_status = "ON" if predicted_light == 1 else "OFF"
        print(f"Received prediction: Light should be {light_status}")
            
    except Exception as e:
        print("Error in message handler:", e)
        # Don't re-raise the exception to prevent MQTT client from crashing

def simulate_sensor_data():
    """Generate random sensor data within reasonable ranges"""
    temperature = round(random.uniform(20, 30), 1)  # 20-30°C
    humidity = round(random.uniform(40, 80), 1)    # 40-80%
    return {
        "temperature": temperature,
        "humidity": humidity
    }

def setup_mqtt():
    """Setup MQTT client and connection"""
    client = mqtt.Client(client_id=MQTT_CLIENT_ID)
    client.on_connect = on_connect
    client.on_message = on_message
    
    try:
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
        return client
    except Exception as e:
        print(f"Failed to connect to MQTT broker: {e}")
        return None

def main():
    print("Starting Smart Mode Test")
    print("This test will simulate sensor data and receive light predictions (0=OFF, 1=ON)")
    
    # Setup MQTT connection
    client = setup_mqtt()
    if client is None:
        print("Failed to setup MQTT. Exiting...")
        return
    
    # Start MQTT loop in a separate thread
    client.loop_start()
    
    try:
        print(f"\nTest will run for {TEST_DURATION} seconds")
        print(f"Sending data every {SEND_INTERVAL} seconds")
        print("\nWaiting for predictions...")
        
        start_time = time.time()
        while time.time() - start_time < TEST_DURATION:
            try:
                # Generate and send sensor data
                sensor_data = simulate_sensor_data()
                client.publish(MQTT_TOPIC_RECEIVE, json.dumps(sensor_data))
                
                print(f"\nSent sensor data:")
                print(f"Temperature: {sensor_data['temperature']}°C")
                print(f"Humidity: {sensor_data['humidity']}%")
                
            except Exception as e:
                print(f"Error sending sensor data: {e}")
            
            # Wait for next interval
            time.sleep(SEND_INTERVAL)
        
        print("\nTest completed!")
        
    except Exception as e:
        print(f"Error during test: {e}")
    
    finally:
        client.loop_stop()
        client.disconnect()

if __name__ == "__main__":
    main() 