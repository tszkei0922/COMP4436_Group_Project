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
import requests
import json
import threading

# Disable SSL verification warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
ssl._create_default_https_context = ssl._create_unverified_context

# InfluxDB configuration
INFLUXDB_URL = "https://us-east-1-1.aws.cloud2.influxdata.com"
INFLUXDB_TOKEN = "k1YKqkvun2CVGuaDCFSzodwsiSoFdHkUsE7_rWBSzf0ubtsq7GYwKPycBbixT5vlt4mVCpxqDXeAe2Z5BYQzvQ=="
INFLUXDB_ORG = "5023c10e3657904b"
INFLUXDB_BUCKET = "COMP4436"

# ThingSpeak Configuration
THINGSPEAK_API_KEY = "YOUR_THINGSPEAK_API_KEY"  # Replace with your ThingSpeak API key
THINGSPEAK_CHANNEL_ID = "YOUR_CHANNEL_ID"  # Replace with your ThingSpeak channel ID
THINGSPEAK_URL = f"https://api.thingspeak.com/channels/{THINGSPEAK_CHANNEL_ID}/feeds.json"

# Global variables
current_model = None

def get_data_from_influxdb():
    """Retrieve data from InfluxDB"""
    client = InfluxDBClient(
        url=INFLUXDB_URL,
        token=INFLUXDB_TOKEN,
        org=INFLUXDB_ORG,
        verify_ssl=False
    )
    
    query_api = client.query_api()
    
    try:
        query = f'''
        from(bucket: "{INFLUXDB_BUCKET}")
            |> range(start: -24h)
            |> filter(fn: (r) => r["_measurement"] == "sensor_data")
            |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
        '''
        
        result = query_api.query_data_frame(query)
        client.close()
        
        if result.empty:
            print("No data retrieved from InfluxDB")
            return None
            
        df = result[['temperature', 'humidity', 'light']].copy()
        # Convert light values to binary (0 or 1)
        df['light'] = (df['light'] > 0).astype(int)
        return df
    
    except Exception as e:
        print(f"Error retrieving data: {e}")
        return None

def train_model(X, y):
    """Train a logistic regression model for binary classification"""
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

def make_prediction(temp, hum):
    """Make a binary prediction (0 or 1) using the current model"""
    global current_model
    if current_model is None:
        print("No model available for prediction")
        return None
    
    try:
        # Get probability of class 1
        prob = current_model.predict_proba([[temp, hum]])[0][1]
        # Convert to binary using 0.5 threshold
        prediction = 1 if prob >= 0.5 else 0
        return prediction
    except Exception as e:
        print(f"Error making prediction: {e}")
        return None

def send_to_thingspeak(temp, hum, prediction):
    """Send data to ThingSpeak"""
    try:
        url = f"https://api.thingspeak.com/update.json"
        payload = {
            "api_key": THINGSPEAK_API_KEY,
            "field1": temp,
            "field2": hum,
            "field3": prediction
        }
        
        response = requests.post(url, data=payload)
        if response.status_code == 200:
            print("Data sent to ThingSpeak successfully")
        else:
            print(f"Failed to send data to ThingSpeak. Status code: {response.status_code}")
    except Exception as e:
        print(f"Error sending data to ThingSpeak: {e}")

def get_latest_sensor_data():
    """Get the latest sensor data from ThingSpeak"""
    try:
        response = requests.get(THINGSPEAK_URL, params={"api_key": THINGSPEAK_API_KEY, "results": 1})
        if response.status_code == 200:
            data = response.json()
            if data['feeds']:
                latest_feed = data['feeds'][0]
                return {
                    'temperature': float(latest_feed['field1']),
                    'humidity': float(latest_feed['field2'])
                }
        return None
    except Exception as e:
        print(f"Error getting data from ThingSpeak: {e}")
        return None

def prediction_loop():
    """Main loop for making predictions and sending to ThingSpeak"""
    global current_model
    
    while True:
        # Get latest sensor data from ThingSpeak
        sensor_data = get_latest_sensor_data()
        
        if sensor_data is not None:
            # Make prediction
            prediction = make_prediction(sensor_data['temperature'], sensor_data['humidity'])
            
            if prediction is not None:
                # Send prediction back to ThingSpeak
                send_to_thingspeak(sensor_data['temperature'], sensor_data['humidity'], prediction)
                print(f"Prediction made: Light should be {'ON' if prediction == 1 else 'OFF'}")
        
        time.sleep(60)  # Check every minute

def train_model_periodically():
    """Periodic model training function"""
    global current_model
    
    while True:
        print("\n=== Starting new training cycle ===")
        print("Fetching data from InfluxDB...")
        
        # Get training data
        df = get_data_from_influxdb()
        
        if df is not None and len(df) > 10:
            # Prepare data
            X = df[['temperature', 'humidity']].values
            y = df['light'].values
            
            # Train model
            print("Training new model...")
            model = train_model(X, y)
            
            # Evaluate model
            predictions = model.predict(X)
            accuracy = accuracy_score(y, predictions)
            report = classification_report(y, predictions)
            
            print("Model Performance:")
            print(f"Accuracy: {accuracy:.2f}")
            print("\nClassification Report:")
            print(report)
            
            # Update current model
            current_model = model
            save_model(model)
        
        else:
            print("Not enough data for training")
        
        print("\nWaiting 5 minutes until next training cycle...")
        time.sleep(300)  # Wait 5 minutes before next training

def main():
    global current_model
    
    print("Starting Light Prediction Service")
    print("Model will predict binary light status (0=OFF, 1=ON)")
    
    # Load existing model if available
    current_model = load_model()
    if current_model is not None:
        print("Loaded existing model")
    else:
        print("No existing model found - will train new model")
    
    # Start training loop in a separate thread
    training_thread = threading.Thread(target=train_model_periodically)
    training_thread.daemon = True
    training_thread.start()
    
    # Start prediction loop in a separate thread
    prediction_thread = threading.Thread(target=prediction_loop)
    prediction_thread.daemon = True
    prediction_thread.start()
    
    try:
        print("\nService is running. Press Ctrl+C to exit.")
        while True:
            time.sleep(1)
    
    except KeyboardInterrupt:
        print("\nShutting down...")

if __name__ == "__main__":
    main()
