import os
import threading
from concurrent.futures import ThreadPoolExecutor
import time
import pytz
import socket
import firebase_admin
from firebase_admin import credentials, db, storage
from datetime import datetime, timedelta


class FirebaseDatabase:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(FirebaseDatabase, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        # Check Firebase initialization status
        if not hasattr(self, '_initialized'):
            self._initialized = True
            self.initialize_firebase_admin()

    @staticmethod
    def get_instance():
        if FirebaseDatabase._instance is None:
            FirebaseDatabase()
        return FirebaseDatabase._instance

    # initialize Firebase Admin SDK
    def initialize_firebase_admin(self):
        # Set path for the credential file
        script_dir = os.path.dirname(os.path.abspath(__file__))
        credentials_path = os.path.join(
            script_dir, 'dtsrs-39010-firebase-adminsdk-1jlzc-61844505e2.json')

        # Authenticate and initialize Firebase Admin SDK
        cred = credentials.Certificate(credentials_path)
        firebase_admin.initialize_app(cred, {
            'databaseURL': 'https://dtsrs-39010-default-rtdb.europe-west1.firebasedatabase.app',
            'storageBucket': 'dtsrs-39010.appspot.com'
        })


def fetch_all_devices():
    ref = db.reference('room/device')
    devices_data = ref.get()
    if devices_data:
        return devices_data
    else:
        return {}


def upload_emergency():
    emergency_ref = db.reference('settings/safety')
    emergency_ref.update({'isEmergency': True})


def upload_manual_emergency(isEmergency):
    if isEmergency:
        emergency_ref = db.reference('settings/safety')
        emergency_ref.update({'isEmergency': True})
    else:
        emergency_ref = db.reference('settings/safety')
        emergency_ref.update({'isEmergency': False})
        current_time = get_time()
        current_time = datetime.strptime(current_time, '%Y-%m-%d %H:%M:%S')
        expirationDatetime = current_time + timedelta(minutes=5)
        expirationDatetime_str = expirationDatetime.strftime("%Y-%m-%d %H:%M:%S")
        emergency_ref.update({'expirationDatetime': expirationDatetime_str})


def fetch_expiration_time():
    emergency_ref = db.reference('settings/safety')
    safety_data = emergency_ref.get()
    expiration_time = safety_data.get("expirationDatetime")
    return expiration_time


def fetch_emergency_status():
    """Fetches emergency status from Firebase."""
    emergency_ref = db.reference('settings/safety')
    emergency_data = emergency_ref.get()
    emergency_status = emergency_data.get('isEmergency') if emergency_data else None
    print("Successfully fetched emergency status")
    print(f"Current emergency status: {emergency_status}")
    return emergency_status


def fetch_target_led_data(device_id):
    light_device_ref = db.reference(f'room/device/light/{device_id}')
    target_data = light_device_ref.get()

    # Check LED configuration data
    if target_data is None:
        print(f'Cannot find target device data：room/device/light/{device_id}')
        return None

    light_data = {
        'id': device_id,
        'name': target_data.get('device_name', None),
        'gpio': target_data.get('gpio', None),
        'brightness': target_data.get('brightness', None),
        'switch': target_data.get('switch', None),
        'auto_mode': target_data.get('auto_mode', None)
    }

    print(f"Light device data of {device_id} fetch successfully.")

    return light_data


def fetch_target_led_rotary_encoder_data(device_id):
    """
        Fetches the target rotary encoder data from the database.

        This function queries the database for the data associated with a
        specific rotary encoder device, identified by its device ID.
        If the data for the requested device is not found, it prints a
        message indicating the absence of the device data and returns None.

        Parameters:
        - device_id (str): The unique identifier for the rotary encoder device.

        Returns:
        - dict or None: The data for the rotary encoder device if found; otherwise, None.
        """
    rotary_encoder_ref = db.reference(f'room/device/light/{device_id}')
    target_data = rotary_encoder_ref.get()

    # Check if the data for the specified device was found.
    if target_data is None:
        print(f'Cannot find target device data: room/device/light/{device_id}')
        return None

    # Return the data for the rotary encoder device if it was successfully found.
    return target_data


def fetch_target_fan_rotary_encoder_data(device_id):
    """
        Fetches the target rotary encoder data from the database.

        This function queries the database for the data associated with a
        specific rotary encoder device, identified by its device ID.
        If the data for the requested device is not found, it prints a
        message indicating the absence of the device data and returns None.

        Parameters:
        - device_id (str): The unique identifier for the rotary encoder device.

        Returns:
        - dict or None: The data for the rotary encoder device if found; otherwise, None.
        """
    rotary_encoder_ref = db.reference(f'room/device/hvac/{device_id}')
    target_data = rotary_encoder_ref.get()

    # Check if the data for the specified device was found.
    if target_data is None:
        print(f'Cannot find target device data: room/device/hvac/{device_id}')
        return None

    # Return the data for the rotary encoder device if it was successfully found.
    return target_data


def fetch_target_light_sensor_data(device_id):
    light_sensor_ref = db.reference(f'room/device/light/{device_id}')
    target_data = light_sensor_ref.get()

    # Check if the target data was found
    if target_data is None:
        print(f'Cannot find target device data: room/device/light/{device_id}')
        return None

    # Return the fetched data for the light sensor device
    return target_data


def fetch_target_dht_sensor_data(device_id):
    dht_sensor_ref = db.reference(f'room/device/hvac/{device_id}')
    target_data = dht_sensor_ref.get()

    # Check if the target data was found
    if target_data is None:
        print(f'Cannot find target device data: room/device/hvac/{device_id}')
        return None

    # Return the fetched data for the light sensor device
    return target_data


def fetch_target_air_sensor_data(device_id):
    air_sensor_ref = db.reference(f'room/device/hvac/{device_id}')
    target_data = air_sensor_ref.get()

    # Check if the target data was found
    if target_data is None:
        print(f'Cannot find target device data: room/device/hvac/{device_id}')
        return None

    # Return the fetched data for the air sensor device
    return target_data


def fetch_target_fan_data(device_id):
    fan_device_ref = db.reference(f'room/device/hvac/{device_id}')
    target_data = fan_device_ref.get()

    # Check if the target data was found
    if target_data is None:
        print(f'Cannot find target device data: room/device/hvac/{device_id}')
        return

    # Compile the Fan device data into a dictionary
    fan_data = {
        'id': device_id,
        'name': target_data.get('device_name'),
        'switch': target_data.get('switch'),
        'gpio': target_data.get('gpio'),
        'speed': target_data.get('speed'),
        'auto_mode': target_data.get('auto_mode'),
        'target': target_data.get('target')
    }

    print(f"Ventilation device data of {device_id} fetch successfully.")
    # Return the fetched data for the fan device
    return fan_data


def fetch_target_flame_sensor_data(device_id):
    flame_sensor_ref = db.reference(f'room/device/safety/{device_id}')
    target_data = flame_sensor_ref.get()

    # Check if the target data was found
    if target_data is None:
        print(f'Cannot find target device data: room/device/safety/{device_id}')
        return None

    # Return the fetched data for the air sensor device
    return target_data


def fetch_target_emergency_light_data(device_id):
    light_ref = db.reference(f'room/device/safety/{device_id}')
    target_data = light_ref.get()

    # Check if the target data was found
    if target_data is None:
        print(f'Cannot find target device data: room/device/safety/{device_id}')
        return None

    # Return the fetched data for the air sensor device
    return target_data


def fetch_target_emergency_trigger_data(device_id):
    device_ref = db.reference(f'room/device/safety/{device_id}')
    target_data = device_ref.get()

    # Check if the target data was found
    if target_data is None:
        print(f'Cannot find target device data: room/device/safety/{device_id}')
        return None

    # Return the fetched data for the air sensor device
    return target_data


def get_time():
    # Get current time in format "YYYY-MM-DD HH:MM:SS"
    amsterdam_timezone = pytz.timezone('Europe/Amsterdam')
    return datetime.now(amsterdam_timezone).strftime("%Y-%m-%d %H:%M:%S")


def upload_light_data_firebase(device_id, switch, brightness, auto_mode):
    current_time = get_time()
    history_ref = db.reference('/light/light/' + device_id + '/' + current_time)
    history_ref.update({'switch': switch, 'brightness': brightness, 'auto_mode': auto_mode})

    ref = db.reference('room/device/light/' + device_id)
    ref.update({'switch': switch, 'brightness': brightness, 'auto_mode': auto_mode})


def upload_light_sensor_data_firebase(device_id, light_intensity):
    current_time = get_time()
    history_ref = db.reference('light/light_sensor/' + device_id + '/' + current_time)
    history_ref.update({'light_intensity': light_intensity})

    ref = db.reference('room/device/light/' + device_id)
    ref.update({'light_intensity': light_intensity})

    print(f"Light intensity data of {device_id} was uploaded successfully.")


def upload_dht_data_firebase(device_id, temperature, humidity):
    current_time = get_time()
    ref = db.reference('hvac/dht_sensor/' + device_id + '/' + current_time)
    ref.update({'temperature': temperature, 'humidity': humidity})
    print(f"DHT data of {device_id} was uploaded successfully.")


def upload_gas_data_firebase(device_id, gas_level):
    """"Upload gas data to firebase"""
    current_time = get_time()
    ref = db.reference('safety/mq_2_sensor/' + device_id + '/' + current_time)
    ref.update({'gas_level': gas_level})
    print(f"Gas level data of {device_id} was uploaded successfully.")


def upload_air_data_firebase(device_id, air_quality):
    current_time = get_time()
    ref = db.reference('hvac/mq_135_sensor/' + device_id + '/' + current_time)
    ref.update({'air_quality': air_quality})


def update_fan_data_firebase(device_id, switch, speed, auto_mode):
    current_time = get_time()
    history_ref = db.reference('hvac/ventilation/' + device_id + '/' + current_time)
    history_ref.update({'switch': switch,
                        'speed': speed,
                        'auto_mode': auto_mode})

    ref = db.reference("room/device/hvac/" + device_id)
    ref.update({'switch': switch,
                'speed': speed,
                'auto_mode': auto_mode})


def upload_flame_data_firebase(device_id, flame_intensity):
    current_time = get_time()
    ref = db.reference('safety/flame_sensor/' + device_id + '/' + current_time)
    ref.update({'flame_intensity': flame_intensity})
    print(f"Flame intensity data of {device_id} was uploaded successfully.")


def upload_ip_address(device_id):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        IP = s.getsockname()[0]
    finally:
        s.close()

    device_type = device_id.split('_')[1]

    if device_type == "security":
        ref_path = f'room/device/security/{device_id}'
    elif device_type == "audio":
        ref_path = f'room/device/audio/{device_id}'
    else:
        print("Unsupported device type")
        return

    ref = db.reference(ref_path)
    ref.update({'ip_address': IP})

    print(f"IP address of {device_id} was uploaded successfully. IP address: {IP}")


def fetch_pc_ip_address():
    try:
        ref = db.reference('settings/general/ip_address')
        pc_ip_address = ref.get()
        print(f"PC IP Address: {pc_ip_address}")
        return pc_ip_address
    except Exception as e:
        print(f"Cannot find PC IP Address {e}")
        return None


def fetch_emergency_audio():
    bucket = storage.bucket()
    emergency_audio_folder = 'remote/safety/'
    blobs = bucket.list_blobs(prefix=emergency_audio_folder)

    download_folder = 'temp_download'
    if not os.path.exists(download_folder):
        os.makedirs(download_folder)

    for blob in blobs:
        if blob.name.endswith('.wav') or blob.name.endswith('.mp3'):
            download_path = os.path.join(download_folder, blob.name.split('/')[-1])
            blob.download_to_filename(download_path)
            print(f"Fetch audio to {download_path}.")
            return download_path
    print(f"Failed to find emergency audio from {emergency_audio_folder}.")
    return None


def add_status_listener(device_id, callback, device_type):
    if device_type == "light":
        ref = db.reference(f'room/device/light/{device_id}')
    elif device_type == "hvac":
        ref = db.reference(f'room/device/hvac/{device_id}')
    else:
        raise ValueError(f"Unknown device type: {device_type}")

    def listener(event):
        if event.data is not None:
            full_data = ref.get()
            callback(full_data)

    def start_listener():
        ref.listen(listener)

    threading.Thread(target=start_listener, daemon=True).start()


def add_light_status_listener(device_id, callback):
    ref = db.reference(f'room/device/light/{device_id}')

    def listener(event):
        if event.data is not None:
            full_data = ref.get()
            callback(full_data)

    def start_listener():
        ref.listen(listener)

    threading.Thread(target=start_listener, daemon=True).start()


def add_fan_status_listener(device_id, callback):
    ref = db.reference(f'room/device/hvac/{device_id}')

    def listener(event):
        if event.data is not None:
            full_data = ref.get()
            callback(full_data)

    def start_listener():
        ref.listen(listener)

    threading.Thread(target=start_listener, daemon=True).start()


def add_emergency_state_listener(callback):
    ref = db.reference('settings/safety')

    def listener(event):
        if event.data is not None:
            full_data = ref.get()
            callback(full_data)

    def start_listener():
        ref.listen(listener)

    threading.Thread(target=start_listener, daemon=True).start()

