# Application that integrates the SGCS with the SHS using the interoperability framework.

import firebase_admin
from firebase_admin import credentials, db, storage
import redis
from time import sleep
import threading
from concurrent.futures import ThreadPoolExecutor

# Redis Configuration
redis_host = 'redis'
redis_port = 6379

#--------------------------------FUNCTIONS---------------------------------------

def redis_upload(sensor_ID, data):
    # Uploading sensor data to redis server
    redis_client.rpush(sensor_ID, data)
    # Maintain list of length 1
    if redis_client.llen(sensor_ID) > 1:
        redis_client.lpop(sensor_ID)

def listener_DHT(event):
        if event.data is not None:
            data = event.data  # This already contains the updated data
            # Process or print the data
            temp = data.get('temperature')
            hum = data.get('humidity')
            if temp is not None:
              print("Temperature:", temp)
              redis_upload("device_hvac_0002_temperature", str(temp))
            if hum is not None:
              print("Humidity:", hum)
              redis_upload("device_hvac_0002_humidity", str(hum))
                
def listener_LightIntensity(event):
        if event.data is not None:
            data = event.data  # This already contains the updated data
            light_intensity = data.get('light_intensity')
            if light_intensity is not None:
              print("Light Intensity:", light_intensity)
              redis_upload("device_light_0010_light_intensity", str(light_intensity))
            
def listener_Light1(event):
        if event.data is not None:
            data = event.data  # This already contains the updated data
            light_status = data.get('switch')
            if light_status is not None:
              print("Light 1 Status:", light_status)
              redis_upload("device_light_0009_light_status", str(light_status))
                
def listener_Light2(event):
        if event.data is not None:
            data = event.data  # This already contains the updated data
            light_status = data.get('switch')
            if light_status is not None:
              print("Light 2 Status:", light_status)
              redis_upload("device_light_0012_light_status", str(light_status))
                
def listener_Fan(event):
        if event.data is not None:
            data = event.data  # This already contains the updated data
            fan_status = data.get('switch')
            if fan_status is not None:
              print("Fan Status:", fan_status)
              redis_upload("device_hvac_0006_fan_status", str(fan_status))
                
def start_listener_DHT():
    ref_DHT.listen(listener_DHT) # Creates a listener
    
def start_listener_LightIntensity():
    ref_LightIntensity.listen(listener_LightIntensity) # Creates a listener
    
def start_listener_Light1():
    ref_Light1.listen(listener_Light1) # Creates a listener
    
def start_listener_Light2():
    ref_Light2.listen(listener_Light2) # Creates a listener
    
def start_listener_Fan():
    ref_Fan.listen(listener_Fan) # Creates a listener

def redis_download(sensor_ID):
    # Retrieve latest item from redis
    last_item = redis_client.lindex(sensor_ID, -1)
    if last_item is None:
        return None
    
    last_item_string = last_item.decode('utf-8')
    print('Message Sent by', sensor_ID, ":", last_item_string)
    return last_item_string

def level_warning(): # Blink emergency light when level of any sensor above 75%
    # Poll required data from redis
    level_Organic = redis_download('L1')
    if level_Organic is not None:
        level_Organic = float(level_Organic)
        change_emergency_status(level_Organic)
        
    level_PMD = redis_download('L2')
    if level_PMD is not None:
        level_PMD = float(level_PMD)
        change_emergency_status(level_PMD)
        
    level_Paper = redis_download('L3')
    if level_Paper is not None:
        level_Paper = float(level_Paper)
        change_emergency_status(level_Paper)

def change_emergency_status(level):
    if level>75.0:
        ref_EmergencyLight.update({'isEmergency': True})
    else:
        ref_EmergencyLight.update({'isEmergency': False})
        
    print("Emergency status changed")
    
        
def temperature_check(): # Blink emergency light when level of any sensor above 75%
    # Poll required data from redis
    #temperature_Organic = float(redis_download('T1'))
    temperature_PMD = float(redis_download('T2'))
    temperature_Paper = float(redis_download('T3'))

    if temperature_PMD and temperature_Paper is not None:
        if temperature_PMD>75.0 or temperature_Paper>75.0:
            ref_EmergencyLight.update({'isEmergency': True})
        else:
            ref_EmergencyLight.update({'isEmergency': False})

#--------------------------------MAIN---------------------------------------

sleep(10)
pathname = "usr/src/app"
# Authenticate and initialize Firebase Admin SDK
cred = credentials.Certificate(pathname)
firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://dtsrs-39010-default-rtdb.europe-west1.firebasedatabase.app',
    'storageBucket': 'dtsrs-39010.appspot.com'
})
    
print("Starting DTSRS APP!")
# Connect to Redis server
redis_client = redis.Redis(host=redis_host, port=redis_port)
print("Connected to REDIS server with port", redis_port)

# REFERENCES TO THE FIREBASE DATABASE FOR SENSORS
ref_DHT = db.reference('hvac/dht_sensor/device_hvac_0002') # DHT sensor
ref_LightIntensity = db.reference('light/light_sensor/device_light_0010') # Light sensor
ref_Light1 = db.reference('light/light/device_light_0009') # White LED
ref_Light2 = db.reference('light/light/device_light_0012') # Yellow LED
ref_Fan = db.reference('hvac/ventilation/device_hvac_0006') # Fan

# REFERENCES TO THE FIREBASE DATABASE FOR ACTUATORS
ref_whiteLED = db.reference('room/device/light/device_light_0009/') # White LED
ref_yellowLED = db.reference('room/device/light/device_light_0012/') # Yellow LED
ref_Fan = db.reference('room/device/hvac/device_hvac_0006')# Fan
ref_EmergencyLight = db.reference('settings/safety') # Emergency Activation

if __name__ == '__main__':
    # START LISTENERS FOR EACH PARAMETER IN A NEW THREAD.
    threading.Thread(target=start_listener_DHT, daemon=True).start()
    threading.Thread(target=start_listener_LightIntensity, daemon=True).start()
    threading.Thread(target=start_listener_Light1, daemon=True).start()
    threading.Thread(target=start_listener_Light2, daemon=True).start()
    threading.Thread(target=start_listener_Fan, daemon=True).start()

    while True:
        level_warning()
        #temperature_check()
        sleep(3)