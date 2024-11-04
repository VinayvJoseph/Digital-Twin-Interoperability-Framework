import time
import threading
import socket
import pyaudio
import wave
import atexit
from pydub import AudioSegment
from pydub.playback import play

from RPi_GPIO_Rotary import rotary
from seeed_dht import DHT
from gpiozero import MCP3008, PWMLED, OutputDevice, PWMOutputDevice, Button, LED
from grove.grove_light_sensor_v1_2 import GroveLightSensor

import firebase_database as fdb


class Device:
    def __init__(self, device_id, detailed_type, gpio_pins):
        self.device_id = device_id
        self.detailed_type = detailed_type
        self.gpio_pins = gpio_pins


class Light(Device):
    def __init__(self, device_id, device_info):
        super().__init__(device_id, "light", device_info["gpio"])
        self.led = None
        self.gpio_pin = device_info["gpio"][0]
        self.bound_devices = device_info.get("bound_devices", [])
        if device_info.get("brightness"):
            self.brightness = device_info["brightness"]
            self.switch = device_info["switch"]
        else:
            self.brightness = 0
            self.switch = False
        self.auto_mode = device_info["auto_mode"]
        self.initialize()

    def initialize(self):
        """Initialize PWM-LED device """
        self.led = PWMLED(self.gpio_pin)
        self.set_brightness(self.brightness)

    def toggle(self):
        """Toggle LED switch"""
        if self.brightness > 0:
            self.set_brightness(0)
        else:
            self.set_brightness(80)

    def set_brightness(self, brightness):
        """Set LED brightness"""
        self.brightness = brightness
        self.switch = brightness > 0
        if self.led is not None:
            self.led.value = self.brightness / 100
        # Upload LED status
        self.upload_status()

    def adjust_brightness(self, change):
        """"Adjust LED brightness value"""
        self.brightness += change
        self.brightness = max(0, min(self.brightness, 100))
        self.set_brightness(self.brightness)
        self.auto_mode = False
        print(f"+++++New brightness: {self.brightness}+++++")

    def handle_listener(self, device_data):
        self.switch = device_data['switch']
        self.auto_mode = device_data['auto_mode']
        self.brightness = device_data['brightness']

        print(f"Light Device {self.device_id}: ")
        print(f"Auto mode: {self.auto_mode}, Brightness: {self.brightness}, Switch: {self.switch}.")

        self.set_brightness(self.brightness)

    def light_adjust(self, all_light_sensors):
        """Adjust LED brightness by Mode"""
        if self.auto_mode:  # Auto Mode
            if all_light_sensors:
                for sensor in all_light_sensors:
                    if self.device_id in sensor.bound_devices:
                        # Change brightness by light intensity
                        self.brightness = sensor.light_intensity
                        break
                # Set light brightness with new value
                self.set_brightness(self.brightness)
                print(f"Light brightness set to {self.brightness}.")
            else:
                print("No bound light sensor detected.")
        else:  # Manual Mode
            pass


    def close(self):
        self.led.close()

    def upload_status(self):
        """Upload LED status to Firebase database"""
        fdb.upload_light_data_firebase(self.device_id, self.switch, self.brightness, self.auto_mode)

    def update_local_led_data(self, device_data):
        """Update local LED info by Firebase database data"""
        self.switch = device_data['switch']
        self.auto_mode = device_data['auto_mode']
        self.brightness = device_data['brightness']

        print(f"Light Device {self.device_id}: ")
        print(f"Auto mode: {self.auto_mode}, Brightness: {self.brightness}, Switch: {self.switch}.")


class RotaryEncoder(Device):
    def __init__(self, device_id, device_info, exist_devices):
        super().__init__(device_id,
                         "light switch",
                         device_info["gpio"])
        self.encoder = None
        self.gpio_pin = device_info["gpio"]
        self.bound_devices = device_info["bound_devices"]
        self.exist_devices = exist_devices
        self.initialize()

    def initialize(self):
        self.encoder = rotary.Rotary(clk=self.gpio_pin[0],
                                     dt=self.gpio_pin[1],
                                     sw=self.gpio_pin[2],
                                     tick=2)
        self.encoder.register(increment=self.increase_brightness,
                              decrement=self.decrease_brightness,
                              pressed=self.toggle_light)
        self.encoder.start()

    def increase_brightness(self):
        for led in self.exist_devices:
            if led.device_id in self.bound_devices:
                led.adjust_brightness(10)
                print(f"+++++Increase brightness of {led.device_id}+++++")

    def decrease_brightness(self):
        for led in self.exist_devices:
            if led.device_id in self.bound_devices:
                led.adjust_brightness(-10)
                print(f"+++++Decrease brightness of {led.device_id}+++++")

    def toggle_light(self):
        for led in self.exist_devices:
            if led.device_id in self.bound_devices:
                led.toggle()
                print(f"+++++Light switch of {self.device_id} pressed+++++")


class LightSensor(Device):
    def __init__(self, device_id, device_info, exist_devices):
        super().__init__(device_id,
                         'light sensor',
                         device_info["gpio"])
        self.gpio_pin = device_info["gpio"][0]
        self.exist_devices = exist_devices
        self.bound_devices = device_info.get("bound_devices", None)
        self.sensor = GroveLightSensor(self.gpio_pin)
        self.light_intensity = device_info["light_intensity"]

    def collect_and_upload_light_intensity(self):
        num_samples = 10
        total_intensity = 0
        for _ in range(num_samples):
            total_intensity += self.sensor.light
            time.sleep(0.1)
        total_intensity = max(total_intensity // 8, 1)
        self.light_intensity = total_intensity / num_samples
        print(f"Current Light Intensity of {self.device_id}: {self.light_intensity}")
        fdb.upload_light_sensor_data_firebase(self.device_id, self.light_intensity)


class DHTSensor(Device):
    def __init__(self, device_id, device_info):
        super().__init__(device_id,
                         'DHT-11 temperature and humidity sensor',
                         device_info['gpio'])
        self.sensor = DHT("11", device_info['gpio'][0])
        self.temperature = 0.0
        self.humidity = 0.0

    def collect_and_upload_dht_data(self):
        """Read data from DHT-11 sensor and update to Firebasee"""
        self.humidity, self.temperature = self.sensor.read()
        if self.humidity is not None and self.temperature is not None:
            print(f"Current Temperature of {self.device_id}: {self.temperature}")
            print(f"Current Humidity of {self.device_id}: {self.humidity}")
            fdb.upload_dht_data_firebase(self.device_id, self.temperature, self.humidity)
        else:
            print(f'Failed to get {self.device_id} data. Try again!')


class MQ2Sensor(Device):
    def __init__(self, device_id, device_info):
        super().__init__(device_id,
                         'MQ-2 gas sensor',
                         device_info['gpio'])
        self.sensor = MCP3008(channel=device_info['gpio'][0])
        self.gas_level = None
        self.threshold = device_info.get("threshold", 50)

    def emergency_check(self):
        if self.gas_level >= self.threshold:
            return True
        else:
            return False

    def collect_and_upload_gas_data(self):
        """Read data from MQ-2 sensor and update to Firebase"""
        self.gas_level = self.sensor.value
        if self.gas_level is not None:
            self.gas_level = round(self.gas_level * 100, 2)
            print(f"Current Gas Level of {self.device_id}: {self.gas_level}")
            fdb.upload_gas_data_firebase(self.device_id, self.gas_level)
        else:
            print(f'Failed to get {self.device_id} data. Try again!')


class MQ135Sensor(Device):
    def __init__(self, device_id, device_info):
        super().__init__(device_id,
                         'MQ-135 air quality sensor',
                         device_info['gpio'])
        self.sensor = MCP3008(channel=device_info['gpio'][0])
        self.air_quality = 0.0
        self.bound_devices = device_info['bound_devices']

    def collect_and_upload_air_data(self):
        """Read data from MQ-135 sensor and update to Firebase"""
        self.air_quality = self.sensor.value
        if self.air_quality is not None:
            self.air_quality = round(self.air_quality * 100, 2)
            print(f"Current Air Quality Level of {self.device_id}: {self.air_quality}")
            fdb.upload_air_data_firebase(self.device_id, self.air_quality)
        else:
            print(f'Failed to get {self.device_id} data. Try again!')


class L9110Fan(Device):
    def __init__(self, device_id, device_info):
        super().__init__(device_id, 'ventilation', device_info['gpio'])
        self.in_a = PWMOutputDevice(device_info['gpio'][0], frequency=100)
        self.in_b = OutputDevice(device_info['gpio'][1])
        self.auto_mode = device_info.get('auto_mode')
        self.switch = device_info.get('switch')
        self.threshold = device_info.get('target', 15)
        self.speed = device_info.get('speed', 0)
        self.upload_status()

    def set_speed(self, speed):
        """Set the fan speed with a limit between 0 and 70."""
        self.speed = max(0, min(speed, 70))
        if self.speed > 0:
            self.in_a.value = speed / 100.0
            self.in_b.off()
            self.switch = True
            self.start_fan(self.speed)
        else:
            self.switch = False
            self.in_a.off()
            self.in_b.off()
            self.stop_fan()

    def start_fan(self, speed=70):
        self.in_a.value = speed / 100.0
        self.speed = speed
        self.in_b.off()
        self.switch = True
        self.upload_status()

    def stop_fan(self):
        self.in_a.off()
        self.in_b.off()
        self.switch = False
        self.speed = 0
        self.upload_status()

    def toggle(self):
        self.switch = not self.switch
        if self.switch:
            self.start_fan()
        else:
            self.stop_fan()

    def auto_adjust(self, all_air_sensors, isEmergency):
        """Auto Adjust fan speed Mode"""
        if self.auto_mode and not isEmergency:  # Auto mode
            print("fan auto mode")
            for sensor in all_air_sensors:
                if self.device_id in sensor.bound_devices:
                    print(f"Sensor value: {sensor.air_quality}, Threshold value: {self.threshold}.")
                    if sensor.air_quality >= self.threshold:
                        print("Air quality is bad.")
                        self.set_speed(min(max(round((sensor.air_quality - self.threshold) * 100), 25), 70))
                        self.start_fan(self.speed)
                    else:
                        print("Air quality is good.")
                        self.stop_fan()
        else:   # Manual mode
            pass

    def handle_listener(self, device_data):
        """Update local fan info by Firebase database data"""
        self.switch = device_data['switch']
        self.auto_mode = device_data['auto_mode']
        self.speed = device_data['speed']
        if self.switch:
            self.start_fan(self.speed)
            print("Listener handler: switch on")
        else:
            self.stop_fan()
            print("Listener handler: switch off")

        print(f"Ventilation Device {self.device_id}: ")
        print(f"Auto mode: {self.auto_mode}, Speed: {self.speed}, Switch: {self.switch}.")

    def update_local_fan_data(self, device_data, isEmergency):
        """Update local fan info by Firebase database data"""
        self.switch = device_data['switch']
        self.auto_mode = device_data['auto_mode']
        self.speed = device_data['speed']
        self.threshold = device_data.get('target', 15)
        if self.switch:
            self.start_fan(self.speed)
        else:
            self.stop_fan()
        print(f"Ventilation Device {self.device_id}: ")
        print(f"Auto mode: {self.auto_mode}, Speed: {self.speed}, Switch: {self.switch}.")

    def upload_status(self):
        """Upload fan status to Firebase database"""
        fdb.update_fan_data_firebase(self.device_id, self.switch, self.speed, self.auto_mode)


class FanRotaryEncoder(Device):
    def __init__(self, device_id, device_info, exist_devices=None):
        super().__init__(device_id,
                         "fan controller",
                         device_info["gpio"])
        self.encoder = None
        self.gpio_pin = device_info["gpio"]
        self.bound_devices = device_info["bound_devices"]
        self.exist_devices = exist_devices
        self.initialize()

    def initialize(self):
        self.encoder = rotary.Rotary(clk=self.gpio_pin[0],
                                     dt=self.gpio_pin[1],
                                     sw=self.gpio_pin[2],
                                     tick=2)
        self.encoder.register(increment=self.increase_speed,
                              decrement=self.decrease_speed,
                              pressed=self.toggle_fan)
        self.encoder.start()

    def increase_speed(self):
        for fan in self.exist_devices:
            if fan.device_id in self.bound_devices:
                new_speed = min(fan.speed + 5, 70)
                fan.set_speed(new_speed)
                print(f"+++++Fan {self.device_id} speed increase, new speed: {new_speed}+++++")
                print(f"{fan.device_id} new speed: {new_speed}")

    def decrease_speed(self):
        for fan in self.exist_devices:
            if fan.device_id in self.bound_devices:
                new_speed = max(fan.speed - 5, 0)
                fan.set_speed(new_speed)
                print(f"+++++Fan {self.device_id} speed decrease, new speed: {new_speed}+++++")

    def toggle_fan(self):
        print(f"+++++Fan switch {self.device_id} pressed+++++")
        for fan in self.exist_devices:
            if fan.device_id in self.bound_devices:
                fan.toggle()
                print(f"{fan.device_id} switched to {'on' if fan.switch else 'off'}")


class FlameSensor(Device):
    def __init__(self, device_id, device_info):
        super().__init__(device_id, 'flame sensor', device_info['gpio'])
        self.sensor = MCP3008(channel=device_info['gpio'][0])
        self.threshold = device_info.get('threshold', 50)
        self.flame_intensity = None

    def collect_and_upload_flame_data(self):
        """Read data from flame sensor and update to Firebase"""
        self.flame_intensity = self.sensor.value
        if self.flame_intensity is not None:
            self.flame_intensity = round(self.flame_intensity * 100, 2)
            print(f"Current Flame intensity of {self.device_id}: {self.flame_intensity}")
            fdb.upload_flame_data_firebase(self.device_id, self.flame_intensity)
        else:
            print(f'Failed to get {self.device_id} data. Try again!')

    def emergency_check(self):
        if self.flame_intensity >= self.threshold:
            return True
        else:
            return False


class EmergencyLight(Device):
    def __init__(self, device_id, device_info):
        super().__init__(device_id, "emergency light", device_info["gpio"])
        self.gpio = device_info["gpio"][0]
        self.led = LED(self.gpio)
        self.emergency_mode = False
        self.blinking_thread = None

    def activate_emergency_mode(self, duration=60, frequency=0.5):
        """Activate the emergency mode by making the light blink in a separate thread."""
        self.emergency_mode = True
        if self.blinking_thread is None or not self.blinking_thread.is_alive():
            self.blinking_thread = threading.Thread(target=self._blink, args=(duration, frequency))
            self.blinking_thread.start()
            print("Emergency light activated.")

    def deactivate_emergency_mode(self):
        """Deactivate the emergency mode and ensure the light is turned off."""
        self.emergency_mode = False
        if self.blinking_thread is not None:
            self.blinking_thread.join()
        self.led.off()
        print("Emergency light deactivated.")

    def _blink(self, duration, frequency):
        """A method that runs in a separate thread to make the light blink."""
        end_time = time.time() + duration
        while time.time() < end_time and self.emergency_mode:
            self.led.toggle()
            time.sleep(frequency / 2)  # Wait for half of the frequency before toggling agai


class EmergencyTrigger(Device):
    def __init__(self, device_id, device_info):
        super().__init__(device_id, 'emergency trigger', device_info['gpio'])
        self.gpio_pin = device_info['gpio'][0]
        self.button = Button(self.gpio_pin, hold_time=3)
        self.button.when_held = self.trigger_emergency

    def trigger_emergency(self):
        isEmergency = fdb.fetch_emergency_status()
        isEmergency = not isEmergency
        fdb.upload_manual_emergency(isEmergency)
        print("Emergency situation uploaded.")


class Speaker(Device):
    def __init__(self, device_id, device_info, audio_path):
        super().__init__(device_id, "speaker", [])
        self.device_id = device_id
        self.upload_ip_address()
        self.start_audio_server()
        self.emergency_audio_lock = threading.Lock()
        self.emergency_audio_playing = False
        self.audio_path = audio_path

    def upload_ip_address(self):
        fdb.upload_ip_address(device_id=self.device_id)

    def start_audio_server(self):
        """Start a background thread to play the received audio data."""
        threading.Thread(target=self.audio_server, daemon=True).start()

    def audio_server(self):
        """Continuously accept connections and handle audio data."""
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        port = 12345
        server_socket.bind(('0.0.0.0', port))
        server_socket.listen(1)
        print("Listening for audio connections...")

        try:
            while True:
                conn, addr = server_socket.accept()
                print(f"Connected by {addr}")
                threading.Thread(target=self.handle_client, args=(conn,), daemon=True).start()
        except Exception as e:
            print("Error handling socket connection: ", e)
        finally:
            server_socket.close()

    def handle_client(self, conn):
        """Handle the audio streaming for a single connection."""
        with self.emergency_audio_lock:
            self.stop_emergency_audio()
            try:
                p = pyaudio.PyAudio()
                stream = p.open(format=pyaudio.paInt16,
                                channels=1,
                                rate=44100,
                                output=True,
                                frames_per_buffer=1024)

                try:
                    while True:
                        data = conn.recv(4096)
                        if data:
                            stream.write(data)
                        else:
                            break
                finally:
                    stream.stop_stream()
                    stream.close()
                    p.terminate()
                    conn.close()
            except Exception as e:
                print("Failed to handle client connection", e)
            finally:
                self.play_emergency_audio()

    def play_emergency_audio(self):
        if self.emergency_audio_playing:
            return
        else:
            try:
                with self.emergency_audio_lock:
                    self.emergency_audio_playing = True

                    if self.audio_path.lower().endswith('.wav'):
                        self.play_wav(self.audio_path)
                    elif self.audio_path.lower().endswith('.mp3'):
                        self.play_mp3(self.audio_path)
                    else:
                        print("Unsupported audio format.")
                        self.emergency_audio_playing = False

            except Exception as e:
                print("Error playing emergency audio:", e)
                self.emergency_audio_playing = False

    def play_wav(self, file_path):
        try:
            wf = wave.open(file_path, 'rb')
            p = pyaudio.PyAudio()
            stream = p.open(format=p.get_format_from_width(wf.getsampwidth()),
                            channels=wf.getnchannels(),
                            rate=wf.getframerate(),
                            output=True)
            data = wf.readframes(1024)
            while data:
                stream.write(data)
                data = wf.readframes(1024)
            stream.stop_stream()
            stream.close()
            p.terminate()
        except Exception as e:
            print("Error playing WAV file:", e)
        finally:
            self.emergency_audio_playing = False

    def play_mp3(self, file_path):
        try:
            audio = AudioSegment.from_mp3(file_path)
            play(audio)
        except Exception as e:
            print("Error playing MP3 file:", e)
        finally:
            self.emergency_audio_playing = False

    def stop_emergency_audio(self):
        self.emergency_audio_playing = False

    def stop_emergency_audio_if_needed(self):
        """Stop the emergency audio if it's playing."""
        with self.emergency_audio_lock:
            if self.emergency_audio_playing:
                self.stop_emergency_audio()
                print(f"Emergency audio stopped for device {self.device_id}.")
