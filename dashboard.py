from flask import Flask, render_template, jsonify
import requests
import json
from datetime import datetime, timedelta
import plotly.graph_objects as go
from plotly.utils import PlotlyJSONEncoder
import threading
import time
import csv
import io
import webbrowser

app = Flask(__name__)

# Configuration
INFLUXDB_URL = "https://us-east-1-1.aws.cloud2.influxdata.com"
INFLUXDB_TOKEN = "QDDpmXr8jhPNEg4F5qV-pJVHs6GxGWgXcQHMmbdjNESY06ohnrNyTngVRS5aFZ8wp0b-3HGHi6pEtbLv-kIdjw=="
INFLUXDB_ORG = "5023c10e3657904b"
INFLUXDB_BUCKET = "COMP4436-2"

# Global variables to store latest data
latest_data = {
    "temperature": None,
    "humidity": None,
    "light": None,
    "timestamp": None
}

def parse_csv_response(csv_data):
    """Parse CSV response from InfluxDB"""
    if not csv_data:
        return None
    
    # Convert CSV string to file-like object
    csv_file = io.StringIO(csv_data)
    reader = csv.DictReader(csv_file)
    
    # Get the last row
    last_row = None
    for row in reader:
        last_row = row
    
    if last_row:
        return {
            "temperature": float(last_row.get('temperature', 0)),
            "humidity": float(last_row.get('humidity', 0)),
            "light": int(last_row.get('light', 0)),
            "timestamp": last_row.get('timestamp', datetime.now().isoformat())
        }
    return None

def fetch_latest_data():
    """Fetch the latest data from InfluxDB"""
    global latest_data
    
    while True:
        try:
            # Query to get the latest data point
            query = f'''
            from(bucket: "{INFLUXDB_BUCKET}")
              |> range(start: -1h)
              |> filter(fn: (r) => r["_measurement"] == "sensor_data")
              |> last()
              |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
            '''
            
            headers = {
                "Authorization": f"Token {INFLUXDB_TOKEN}",
                "Accept": "text/csv",
                "Content-Type": "application/json"
            }
            
            response = requests.post(
                f"{INFLUXDB_URL}/api/v2/query?org={INFLUXDB_ORG}",
                headers=headers,
                json={"query": query}
            )
            
            if response.status_code == 200:
                data = parse_csv_response(response.text)
                if data:
                    latest_data = data
            
        except Exception as e:
            print(f"Error fetching data: {e}")
        
        time.sleep(5)  # Update every 5 seconds

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/data')
def get_data():
    return jsonify(latest_data)

@app.route('/chart')
def get_chart():
    try:
        # Query to get historical data for the last hour
        query = f'''
        from(bucket: "{INFLUXDB_BUCKET}")
          |> range(start: -1h)
          |> filter(fn: (r) => r["_measurement"] == "sensor_data")
          |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
        '''
        
        headers = {
            "Authorization": f"Token {INFLUXDB_TOKEN}",
            "Accept": "text/csv",
            "Content-Type": "application/json"
        }
        
        response = requests.post(
            f"{INFLUXDB_URL}/api/v2/query?org={INFLUXDB_ORG}",
            headers=headers,
            json={"query": query}
        )
        
        if response.status_code == 200:
            # Parse CSV data
            csv_file = io.StringIO(response.text)
            reader = csv.DictReader(csv_file)
            
            # Process data for plotting
            times = []
            temperatures = []
            humidities = []
            lights = []
            
            for row in reader:
                times.append(row['_time'])
                temperatures.append(float(row.get('temperature', 0)))
                humidities.append(float(row.get('humidity', 0)))
                lights.append(int(row.get('light', 0)))
            
            # Create temperature plot
            temp_fig = go.Figure()
            temp_fig.add_trace(go.Scatter(
                x=times,
                y=temperatures,
                name='Temperature',
                line=dict(color='red', width=2)
            ))
            temp_fig.update_layout(
                title='Temperature Over Time',
                xaxis_title='Time',
                yaxis_title='Temperature (Â°C)',
                hovermode='x unified',
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                font=dict(family='Roboto'),
                xaxis=dict(gridcolor='rgba(0,0,0,0.1)'),
                yaxis=dict(gridcolor='rgba(0,0,0,0.1)')
            )
            
            # Create humidity plot
            humidity_fig = go.Figure()
            humidity_fig.add_trace(go.Scatter(
                x=times,
                y=humidities,
                name='Humidity',
                line=dict(color='blue', width=2)
            ))
            humidity_fig.update_layout(
                title='Humidity Over Time',
                xaxis_title='Time',
                yaxis_title='Humidity (%)',
                hovermode='x unified',
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                font=dict(family='Roboto'),
                xaxis=dict(gridcolor='rgba(0,0,0,0.1)'),
                yaxis=dict(gridcolor='rgba(0,0,0,0.1)')
            )
            
            # Create light/fan status plot
            light_fig = go.Figure()
            light_fig.add_trace(go.Scatter(
                x=times,
                y=lights,
                name='Air-conditioning Status',
                line=dict(color='green', width=2)
            ))
            light_fig.update_layout(
                title='Air-conditioning Status Over Time',
                xaxis_title='Time',
                yaxis_title='Status (0=ON, 1=OFF)',
                hovermode='x unified',
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                font=dict(family='Roboto'),
                xaxis=dict(gridcolor='rgba(0,0,0,0.1)'),
                yaxis=dict(
                    gridcolor='rgba(0,0,0,0.1)',
                    tickmode='array',
                    tickvals=[0, 1],
                    ticktext=['ON', 'OFF'],
                    autorange='reversed'
                )
            )
            
            return jsonify({
                'temperature': json.loads(temp_fig.to_json()),
                'humidity': json.loads(humidity_fig.to_json()),
                'light': json.loads(light_fig.to_json())
            })
            
    except Exception as e:
        print(f"Error creating charts: {e}")
        return jsonify({"error": str(e)})

if __name__ == '__main__':
    # Start the data fetching thread
    data_thread = threading.Thread(target=fetch_latest_data)
    data_thread.daemon = True
    data_thread.start()
    
    # Run the Flask app
    app.run(debug=True, host='0.0.0.0', port=5000) 
    time.sleep(10)  # Give the server a moment to start
    webbrowser.open('http://localhost:5000')