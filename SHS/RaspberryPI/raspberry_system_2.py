import time
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
import pytz
import gpiozero
import firebase_database as fdb
from devices import (Light, RotaryEncoder, LightSensor,
                     DHTSensor, MQ135Sensor, L9110Fan, FanRotaryEncoder,
                     MQ2Sensor, FlameSensor, EmergencyLight, EmergencyTrigger,
                     Speaker)


rpi_id = '1'


def fetch_devices_by_rpi_id(rpi):
    """Fetches devices by RPI ID from Firebase database."""
    all_devices = {}

    basic_device_types = {
        "light": Light,
        "temperature and humidity sensor": DHTSensor,
        "ventilation": L9110Fan,
        "air sensor": MQ135Sensor,
        "flame sensor": FlameSensor,
        "gas sensor": MQ2Sensor,
        "emergency light": EmergencyLight,
        "emergency button": EmergencyTrigger,
        "speaker": Speaker
    }

    dependent_device_types = {
        "light rotary encoder": RotaryEncoder,
        "light intensity sensor": LightSensor,
        "fan controller": FanRotaryEncoder
    }

    target_paths = ["light", "hvac", "safety", "audio"]
    devices_data = fdb.fetch_all_devices()

    print("----------------------------------------------------------")
    print(f"Starting Instantiate Devices from Firebase by RPI ID: {rpi_id}")
    print("Device ids: ")
    audio_file_path = fdb.fetch_emergency_audio()

    # First instantiate the basic device
    for path, devices in devices_data.items():
        if any(target in path for target in target_paths):
            for device_id, info in devices.items():
                if info.get('rpi_id', None) == rpi:
                    device_class = basic_device_types.get(info.get("detailed_type"))
                    if device_class:
                        if device_class == Light:
                            fdb_info = fdb.fetch_target_led_data(device_id=device_id)
                            device_instance = device_class(
                                device_id=device_id,
                                device_info=fdb_info
                            )
                        elif device_class == Speaker:
                            device_instance = device_class(device_id=device_id, device_info=info, audio_path=audio_file_path)
                        else:
                            device_instance = device_class(device_id=device_id, device_info=info)
                        print(device_id)
                        all_devices.setdefault(info["detailed_type"], []).append(device_instance)

    # Then instantiate the dependent device
    for path, devices in devices_data.items():
        if any(target in path for target in target_paths):
            for device_id, info in devices.items():
                if info.get('rpi_id', None) == rpi:
                    device_class = dependent_device_types.get(info.get("detailed_type"))
                    if device_class:
                        device_instance = None
                        if device_class == RotaryEncoder:
                            device_instance = device_class(
                                device_id=device_id,
                                device_info=info,
                                exist_devices=all_devices.get("light", [])
                            )
                        elif device_class == LightSensor:
                            device_instance = device_class(
                                device_id=device_id,
                                device_info=info,
                                exist_devices=all_devices.get("light", [])
                            )
                        elif device_class == FanRotaryEncoder:
                            device_instance = device_class(
                                device_id=device_id,
                                device_info=info,
                                exist_devices=all_devices.get("ventilation", [])
                            )

                        print(device_id)
                        all_devices.setdefault(info["detailed_type"], []).append(device_instance)
    print("Instantiation Complete.")
    print("----------------------------------------------------------")
    return all_devices


def setup_listeners(all_devices):
    """Set up Firebase listeners for each light device."""
    for light in all_devices.get("light", []):
        fdb.add_light_status_listener(light.device_id, light.handle_listener)

    for fan in all_devices.get("ventilation", []):
        fdb.add_fan_status_listener(fan.device_id, fan.handle_listener)


def collect_and_upload_data(all_devices):
    """Collect data from sensors and upload to Firebase."""
    print("Start Collecting Data from Sensors")

    # Safety Subsystem
    for gas_sensor in all_devices.get("gas sensor", []):
        gas_sensor.collect_and_upload_gas_data()

    for flame_sensor in all_devices.get("flame sensor", []):
        flame_sensor.collect_and_upload_flame_data()

    # Light Subsystem
    for light_sensor in all_devices.get("light intensity sensor", []):
        light_sensor.collect_and_upload_light_intensity()

    # HVAC Subsystem
    for dht_sensor in all_devices.get("temperature and humidity sensor", []):
        dht_sensor.collect_and_upload_dht_data()

    for air_sensor in all_devices.get("air sensor", []):
        air_sensor.collect_and_upload_air_data()
    print("Data Successfully Collected")
    print("----------------------------------------------------------")


def update_data_from_firebase_and_control_devices(all_devices, isEmergency):
    """Update device state based on data from Firebase. And control devices."""
    print("----------------------------------------------------------")
    print("Updating Data to Local Devices from Firebase")
    for light_device in all_devices.get("light", []):
        light_info = fdb.fetch_target_led_data(device_id=light_device.device_id)
        light_device.update_local_led_data(light_info)
        light_device.light_adjust(all_devices.get("light intensity sensor", []))

    for fan_device in all_devices.get("ventilation", []):
        fan_info = fdb.fetch_target_fan_data(device_id=fan_device.device_id)
        fan_device.update_local_fan_data(fan_info, isEmergency)
        fan_device.auto_adjust(all_devices.get("air sensor", []), isEmergency)


def check_safety_devices(all_devices):
    emergency_result = False
    for gas_sensor_device in all_devices.get("gas sensor", []):
        if gas_sensor_device.emergency_check():
            emergency_result = True
            break
    for flame_sensor_device in all_devices.get("flame sensor", []):
        if flame_sensor_device.emergency_check():
            emergency_result = True
            break
    return emergency_result


def determine_emergency(isFirebaseEmergency, isLocalEmergency):
    expiration_time_str = fdb.fetch_expiration_time()
    current_time_str = fdb.get_time()

    expiration_time = datetime.strptime(expiration_time_str, "%Y-%m-%d %H:%M:%S")
    current_time = datetime.strptime(current_time_str, "%Y-%m-%d %H:%M:%S")

    if isFirebaseEmergency:
        return True
    elif isLocalEmergency and current_time >= expiration_time:
        return True
    else:
        return False


def handle_emergency(all_devices, is_emergency):
    """Handle emergency situations."""
    print("----------------------------------------------------------")

    if is_emergency:
        print("Emergency Detected!")
        for fan_device in all_devices.get("ventilation", []):
            fan_device.stop_fan()
        for emergency_light_device in all_devices.get("emergency light", []):
            emergency_light_device.activate_emergency_mode()
        for speaker in all_devices.get("speaker", []):
            speaker.play_emergency_audio()
    else:
        print("No Emergency Detected.")
        for emergency_light_device in all_devices.get("emergency light", []):
            emergency_light_device.deactivate_emergency_mode()
        for speaker in all_devices.get("speaker", []):
            speaker.stop_emergency_audio_if_needed()
    print("----------------------------------------------------------")


def cleanup_devices(all_devices):
    """Clean up and close all devices safely."""
    for device_type, device_list in all_devices.items():
        for temp_device in device_list:
            if hasattr(temp_device, 'close'):
                print(f"{temp_device.device_id} clean up.")
                temp_device.close()


def main_loop(all_devices):
    """Main operational loop."""
    isEmergency = False
    expirationDatetime_str = None

    def handler_emergency_listener(full_data):
        print("Handling Emergency Listener...")
        global isEmergency, expirationDatetime_str
        isEmergency = full_data.get('isEmergency', False)
        expirationDatetime_str = full_data.get('expirationDatetime', None)
        handle_emergency(all_devices, isEmergency)

    setup_listeners(all_devices)
    fdb.add_emergency_state_listener(handler_emergency_listener)

    try:
        while True:
            collect_and_upload_data(all_devices)
            isEmergency = fdb.fetch_emergency_status()
            isLocalEmergency = check_safety_devices(all_devices)
            isEmergency = determine_emergency(isEmergency, isLocalEmergency)
            update_data_from_firebase_and_control_devices(all_devices, isEmergency)
            handle_emergency(all_devices, isEmergency)

            time.sleep(10)

    except KeyboardInterrupt:
        print("Exiting...")
    finally:
        cleanup_devices(all_devices)


if __name__ == '__main__':
    # Initialize and instantiate Firebase module
    fdb.FirebaseDatabase.get_instance()
    # Fetch all device of specific rpi_id
    devices = fetch_devices_by_rpi_id(rpi_id)

    main_loop(devices)
