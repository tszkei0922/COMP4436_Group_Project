from influxdb_client import InfluxDBClient
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report
import time
import pickle
import os
import urllib3
import ssl
import paho.mqtt.client as mqtt
import json
import threading
from datetime import datetime

# Disable SSL verification warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
ssl._create_default_https_context = ssl._create_unverified_context

# InfluxDB configuration
INFLUXDB_URL = "https://us-east-1-1.aws.cloud2.influxdata.com"
#INFLUXDB_TOKEN = "k1YKqkvun2CVGuaDCFSzodwsiSoFdHkUsE7_rWBSzf0ubtsq7GYwKPycBbixT5vlt4mVCpxqDXeAe2Z5BYQzvQ=="
INFLUXDB_TOKEN = "QDDpmXr8jhPNEg4F5qV-pJVHs6GxGWgXcQHMmbdjNESY06ohnrNyTngVRS5aFZ8wp0b-3HGHi6pEtbLv-kIdjw==" #new
INFLUXDB_ORG = "5023c10e3657904b"
#INFLUXDB_BUCKET = "COMP4436"
INFLUXDB_BUCKET = "COMP4436-2"

# MQTT Configuration
MQTT_BROKER = "broker.hivemq.com"
MQTT_PORT = 1883
MQTT_CLIENT_ID = "model_predictor"
MQTT_TOPIC_RECEIVE = "esp32/sensor_data"
MQTT_TOPIC_SEND = "esp32/predicted_light"

# Global variables
current_model = None
mqtt_client = None

def get_data_from_influxdb():
    """Retrieve data from InfluxDB"""
    client = InfluxDBClient(
        url=INFLUXDB_URL,
        token=INFLUXDB_TOKEN,
        org=INFLUXDB_ORG,
        verify_ssl=False
    )
    
    query_api = client.query_api()
    #|> range(start: -24h)
    try:
        query = f'''
        from(bucket: "{INFLUXDB_BUCKET}")
            |> range(start: 0)
            |> filter(fn: (r) => r["_measurement"] == "sensor_data")
            |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
        '''
        
        result = query_api.query_data_frame(query)
        client.close()
        
        if result.empty:
            print("No data retrieved from InfluxDB")
            return None
            
        # Convert time to datetime and extract time features
        df = result[['_time', 'temperature', 'humidity', 'light']].copy()
        df['hour'] = df['_time'].dt.hour
        df['minute'] = df['_time'].dt.minute
        df['day_of_week'] = df['_time'].dt.dayofweek
        df['is_night'] = ((df['hour'] >= 20) | (df['hour'] <= 6)).astype(int)
        
        return df
    
    except Exception as e:
        print(f"Error retrieving data: {e}")
        return None

def train_model(X, y):
    """Train a logistic regression model with time features"""
    model = LogisticRegression()
    model.fit(X, y)
    return model

def save_model(model, filename='light_predictor_model.pkl'):
    """Save the trained model to a file"""
    try:
        with open(filename, 'wb') as f:
            pickle.dump(model, f)
        print(f"Model saved to {filename}")
    except Exception as e:
        print(f"Error saving model: {e}")

def load_model(filename='light_predictor_model.pkl'):
    """Load the trained model from a file"""
    if os.path.exists(filename):
        try:
            with open(filename, 'rb') as f:
                return pickle.load(f)
        except Exception as e:
            print(f"Error loading model: {e}")
    return None

def make_prediction(temp, hum, current_time=None):
    """Make a prediction using the current model with time features"""
    global current_model
    if current_model is None:
        print("No model available for prediction")
        return None
    
    try:
        if current_time is None:
            current_time = datetime.now()
        
        # Create time features for prediction
        hour = current_time.hour
        minute = current_time.minute
        day_of_week = current_time.weekday()
        is_night = 1 if (hour >= 20 or hour <= 6) else 0
        
        # Prepare features array with time features
        features = np.array([[temp, hum, hour, minute, day_of_week, is_night]])
        
        # Get binary prediction (0 or 1)
        prediction = current_model.predict(features)[0]
        return prediction
    except Exception as e:
        print(f"Error making prediction: {e}")
        return None

# MQTT Callbacks
def on_connect(client, userdata, flags, rc):
    print(f"Connected to MQTT broker with result code {rc}")
    client.subscribe(MQTT_TOPIC_RECEIVE)
    print(f"Subscribed to {MQTT_TOPIC_RECEIVE}")

def on_message(client, userdata, msg):
    """Handle incoming MQTT messages"""
    try:
        # Parse the incoming JSON message
        data = json.loads(msg.payload.decode())
        temp = data['temperature']
        hum = data['humidity']
        print(f"\nReceived request for prediction:")
        print(f"Temperature: {temp}Â°C, Humidity: {hum}%")

        # Make prediction with current time
        prediction = make_prediction(temp, hum)
        
        if prediction is not None:
            # Send prediction back via MQTT
            client.publish(MQTT_TOPIC_SEND, str(prediction))
            print(f"Sent prediction: {prediction}")
        
    except Exception as e:
        print(f"Error processing message: {e}")

def train_model_periodically():
    """Periodic model training function"""
    global current_model
    
    while True:
        print("\n=== Starting new training cycle ===")
        print("Fetching data from InfluxDB...")
        
        # Get training data
        df = get_data_from_influxdb()
        
        if df is not None and len(df) > 10:
            # Prepare data with time features
            X = df[['temperature', 'humidity', 'hour', 'minute', 'day_of_week', 'is_night']].values
            
            # Convert light values to binary classification (1 if light > threshold, 0 otherwise)
            light_threshold = df['light'].median()
            y = (df['light'] > light_threshold).astype(int)
            
            # Train model
            print("Training new model...")
            model = train_model(X, y)
            
            # Evaluate model
            predictions = model.predict(X)
            accuracy = accuracy_score(y, predictions)
            
            print("Model Performance:")
            print(f"Accuracy: {accuracy:.2f}")
            print("\nClassification Report:")
            print(classification_report(y, predictions))
            
            # Update current model
            current_model = model
            save_model(model)
        
        else:
            print("Not enough data for training")
        
        print("\nWaiting 5 minutes until next training cycle...")
        time.sleep(300)  # Wait 5 minutes before next training

def setup_mqtt():
    """Setup MQTT client and connection"""
    global mqtt_client
    
    mqtt_client = mqtt.Client(client_id=MQTT_CLIENT_ID)
    mqtt_client.on_connect = on_connect
    mqtt_client.on_message = on_message
    
    try:
        mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
        return True
    except Exception as e:
        print(f"Failed to connect to MQTT broker: {e}")
        return False

def main():
    global current_model, mqtt_client
    
    print("Starting Light Prediction Service")
    
    # Load existing model if available
    current_model = load_model()
    if current_model is not None:
        print("Loaded existing model")
    else:
        print("No existing model found - will train new model")
    
    # Setup MQTT connection
    if not setup_mqtt():
        print("Failed to setup MQTT. Exiting...")
        return
    
    # Start MQTT loop in a separate thread
    mqtt_client.loop_start()
    
    # Start training loop in a separate thread
    training_thread = threading.Thread(target=train_model_periodically)
    training_thread.daemon = True
    training_thread.start()
    
    try:
        print("\nService is running. Press Ctrl+C to exit.")
        while True:
            time.sleep(1)
    
    except KeyboardInterrupt:
        print("\nShutting down...")
        mqtt_client.loop_stop()
        mqtt_client.disconnect()

if __name__ == "__main__":
    main()