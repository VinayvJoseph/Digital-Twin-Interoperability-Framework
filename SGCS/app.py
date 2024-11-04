# SGCS application code.
import os
import socket
import fcntl
import struct
import sys
import asyncio
import websockets
import json
from threading import Thread
import Adafruit_DHT
import time
import RPi.GPIO as GPIO
import firebase_admin
from firebase_admin import credentials, db
import datetime
import redis

#-----------------------------------------------CONFIGURATION---------------------------------------------

# Configurable parameters
port = 8080 # Websocket port
database_upload_interval = 300 # Uploads every 5 minutes
bin_height = 42.0 #cm

# Redis
redis_host = 'localhost'
redis_port = 6379

#----------------------------------------------GLOBAL VARIABLES---------------------------------------------

# Global variables to store sensor data
t1=0.0; h1=0.0; d1=0.0; t2=0.0; h2=0.0; d2=0.0; t3=0.0; h3=0.0; d3=0.0;
DB=[1,1,1,1,1,1,1,1,1] # variable to decide which sensor data is uploaded to the cloud
simulation_flag = 0 # Simulation/Physical mode flag
LED_Organic = False; LED_PMD = False; LED_Paper = False ;

# JSON message key/value pair initialisation.
sensor_reading = {
    'Timestamp': '',
    'Temperature_Organic': t1,
    'Humidity_Organic': h1,
    'Distance_Organic': d1,
    'Temperature_PMD': t2,
    'Humidity_PMD': h2,
    'Distance_PMD': d2,
    'Temperature_Paper': t3,
    'Humidity_Paper': h3,
    'Distance_Paper': d3,
    'Organic_isFull': LED_Organic,
    'PMD_isFull' : LED_PMD,
    'Paper_isFull': LED_Paper
}

# Pin Assingment
GPIO.setmode(GPIO.BCM)
DHT_SENSOR = Adafruit_DHT.DHT22
DHT_PIN_Organic = 2
DHT_PIN_PMD = 3
DHT_PIN_Paper = 4

GPIO_TRIGGER_Organic = 17
GPIO_ECHO_Organic = 18
GPIO_TRIGGER_PMD = 27
GPIO_ECHO_PMD = 23
GPIO_TRIGGER_Paper = 22
GPIO_ECHO_Paper = 24

LED_PIN_Organic = 10
LED_PIN_PMD = 9
LED_PIN_Paper = 11

#Set GPIO direction (IN / OUT)
GPIO.setup(GPIO_TRIGGER_Organic, GPIO.OUT)
GPIO.setup(GPIO_ECHO_Organic, GPIO.IN)
GPIO.setup(DHT_PIN_Organic, GPIO.IN)
GPIO.setup(GPIO_TRIGGER_PMD, GPIO.OUT)
GPIO.setup(GPIO_ECHO_PMD, GPIO.IN)
GPIO.setup(DHT_PIN_PMD, GPIO.IN)
GPIO.setup(GPIO_TRIGGER_Paper, GPIO.OUT)
GPIO.setup(GPIO_ECHO_Paper, GPIO.IN)
GPIO.setup(DHT_PIN_Paper, GPIO.IN)
GPIO.setup(LED_PIN_Organic, GPIO.OUT)
GPIO.setup(LED_PIN_PMD, GPIO.OUT)
GPIO.setup(LED_PIN_Paper, GPIO.OUT)

#-----------------------------------------------------------------------------------------FUNCTIONS----------------------------------------------------------------------------

# Websocket Communication with Unity(websocket client)
async def server(websocket, path):
    print("Server Running on port : ", port)
    global sensor_reading, t1, h1, d1, t2, h2, d2, t3, h3, d3, simulation_flag, LED_Organic, LED_PMD, LED_Paper;

    try:
        while True:
            if simulation_flag==0:
                current_time = datetime.datetime.now()
                current_time_str = current_time.strftime("%Y-%m-%d %H:%M:%S")

                # Temperature and Humidity polling from DHT sensors
                #h1, t1 = DHT_sensor(DHT_PIN_Organic)
                #redis_upload('H1', h1); redis_upload('T1', t1); 
                h2, t2 = DHT_sensor(DHT_PIN_PMD)
                redis_upload('H2', h2); redis_upload('T2', t2); 
                h3, t3 = DHT_sensor(DHT_PIN_Paper)
                redis_upload('H3', h3); redis_upload('T3', t3); 

                # Level Measurement with ultrasonic sensors
                d1 = distance(GPIO_TRIGGER_Organic, GPIO_ECHO_Organic)
                redis_upload('L1', d1)
                d2 = distance(GPIO_TRIGGER_PMD, GPIO_ECHO_PMD)
                redis_upload('L2', d2)
                d3 = distance(GPIO_TRIGGER_Paper, GPIO_ECHO_Paper)
                redis_upload('L3', d3)

                # Assign sensor data 'value' to respective 'key' in the dict.
                sensor_reading = {
                'Timestamp' : current_time_str,
                'Temperature_Organic': t1, 'Humidity_Organic': h1, 'Distance_Organic': d1,
                'Temperature_PMD': t2, 'Humidity_PMD': h2, 'Distance_PMD': d2,
                'Temperature_Paper': t3, 'Humidity_Paper': h3, 'Distance_Paper': d3,
                'Organic_isFull': LED_Organic, 'PMD_isFull' : LED_PMD, 'Paper_isFull': LED_Paper
                }

                # Send real-time sensor data to the websocket client
                await websocket.send(json.dumps(sensor_reading))
                await asyncio.sleep(0.2)  # Adjust the interval as needed

            # Wait for data from the client (non-blocking)
            try:
                data_from_client = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                if data_from_client == "Simulation Mode" and simulation_flag==0:
                    simulation_flag = 1
                    print(f"Received from client: {data_from_client}")

                if simulation_flag == 1:
                    client_data = await websocket.recv()
                    if client_data == "Physical Mode":
                        simulation_flag = 0
                        print(f"Received from client: {client_data}")
                        continue

                    # Receiving json data from Unity.
                    data = json.loads(client_data)
                    print("Receiving Data from Unity")

                    # Storing Unity data into global varibales.
                    t1 = data['Temperature_Organic'];h1 = data['Humidity_Organic'];d1 = data['Distance_Organic']; LED_Organic = data['Organic_isFull'];
                    t2 = data['Temperature_PMD']; h2 = data['Humidity_PMD']; d2 = data['Distance_PMD']; LED_PMD = data['PMD_isFull'];
                    t3 = data['Temperature_Paper']; h3 = data['Humidity_Paper']; d3 = data['Distance_Paper']; LED_Paper = data['Paper_isFull'];

            except asyncio.TimeoutError:
                pass

            # Updating LEDs
            if d1>75:
                LED_Organic = True
            else:
                LED_Organic = False
            if d2>75:
                LED_PMD = True
            else:
                LED_PMD = False
            if d3>75:
                LED_Paper = True
            else:
                LED_Paper = False

            GPIO.output(LED_PIN_Organic, LED_Organic)
            GPIO.output(LED_PIN_PMD, LED_PMD)
            GPIO.output(LED_PIN_Paper, LED_Paper)


    except websockets.ConnectionClosed:
        print("Client disconnected")


# Function to upload data to redis server
def redis_upload(sensor_ID, data):
    # Uploading sensor data to redis server
    redis_client.rpush(sensor_ID, data)

    # Maintain list of length 1
    if redis_client.llen(sensor_ID) > 1:
        redis_client.lpop(sensor_ID)

# Function to upload sensor data to the real-time database in firebase.
def upload_database():
    global sensor_reading, database_upload_interval, DB;
    Key = ['Temperature_Organic', 'Humidity_Organic', 'Distance_Organic','Temperature_PMD', 'Humidity_PMD', 'Distance_PMD','Temperature_Paper', 'Humidity_Paper', 'Distance_Paper']
    while True:
        time.sleep(database_upload_interval)
        database_reading ={'Timestamp':sensor_reading['Timestamp']}
        Value = [sensor_reading[Key[0]], sensor_reading[Key[1]], sensor_reading[Key[2]],sensor_reading[Key[3]], sensor_reading[Key[4]], sensor_reading[Key[5]],
                 sensor_reading[Key[6]], sensor_reading[Key[7]], sensor_reading[Key[8]]]

        # Data selection based on input from display
        for i in range(9):
            #if DB[i]!=0:
            database_reading[Key[i]] = Value[i]

        # Send data to the database
        if database_reading["Timestamp"] == '' :
            continue;
        ref.child(database_reading['Timestamp']).set(database_reading)
        print("Data sent to firebase")
        database_reading = {}

# Function to read humidity and temperature data from DHT sensor
def DHT_sensor(DHT_PIN):
    try:
        hum, temp = Adafruit_DHT.read_retry(DHT_SENSOR, DHT_PIN, retries=3)
        if hum is not None and temp is not None:
            hum = round(hum, 3)
            temp = round(temp, 3)
        else:
            temp=999; hum=999;
            print("Failed to read PMD DHT sensor.")
    except Exception as e:
        print(f"Error reading PMD sensor data: {str(e)}")

    return hum, temp

# Function to measure distance using ultraosnic sensors
def distance(trigger, echo):
        global bin_height
        GPIO.output(trigger, True)
        time.sleep(0.00001)
        GPIO.output(trigger, False)

        StartTime = time.time()
        StopTime = time.time()
        while GPIO.input(echo) == 0:
            StartTime = time.time()
        while GPIO.input(echo) == 1:
            StopTime = time.time()

        TimeElapsed = StopTime - StartTime
        distance = (TimeElapsed * 34300) / 2
        distance = round(100-(distance/bin_height*100),3);
        time.sleep(0.1)
        return distance

# Function to Retrive latest ip address of raspberry pi
def get_ip_address(ifname):
 s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
 return socket.inet_ntoa(fcntl.ioctl(
 s.fileno(),
 0x8915, # SIOCGIFADDR
 struct.pack('256s', ifname[:15].encode('utf-8'))
    )[20:24])

# Function to start websocket communication event loop in a separate thread
def start_event_loop():
    loop.run_until_complete(start_server)
    loop.run_forever()

#-----------------------------------------------------------------------MAIN----------------------------------------------------------------

# Initialize Firebase Admin SDK with your downloaded credentials
cred = credentials.Certificate('/home/digitaltwin/SGCS/firebase_credentials.json')
firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://sgcs-1f60d-default-rtdb.firebaseio.com/'
})

ref = db.reference('Sensor_Data')


# Connect to Redis server
redis_client = redis.Redis(host=redis_host, port=redis_port)
print("Connected to REDIS server with port", redis_port)

# Retrieve latest ip.
server_ip = get_ip_address('wlan0')
#print("Wifi: ", get_ip_address('wlan0'))

# Start server
start_server = websockets.serve(server, server_ip, port)

# Create event loop
loop = asyncio.get_event_loop()

# Start the event loop in a separate thread. Three different threads are created and initiated.
event_loop_thread = Thread(target=start_event_loop)
upload_thread = Thread(target=upload_database)
event_loop_thread.start() # Beginning execution of Websocket communication thread.
upload_thread.start() # Beginning execution of database upload to Firebase thread.
