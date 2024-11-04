import firebase_admin
from firebase_admin import credentials, db
from signal import pause
import firebase_database as fdb
import RPi.GPIO as GPIO
import time
import sys


class Keypad:
    def __init__(self, rows, cols):
        self.rows = rows
        self.cols = cols
        self.layout = [
            ["1", "2", "3"],
            ["4", "5", "6"],
            ["7", "8", "9"],
            ["*", "0", "#"]
        ]
        self.setup_pins()
        self.previous_state = {}
        self.input_timeout = 15
        self.last_input_time = time.time()

    @staticmethod
    def get_device_info(rpi_id):
        ref = db.reference('room/device/security')
        devices = ref.get()
        for device_id, details in devices.items():
            if details['detailed_type'] == "access keypad" and details['rpi_id'] == rpi_id:
                gpio_settings = details.get('gpio', "")
                if len(gpio_settings) == 7:
                    rows = [int(pin) for pin in gpio_settings[:4]]
                    cols = [int(pin) for pin in gpio_settings[4:7]]
                    return rows, cols
                else:
                    raise ValueError("GPIO settings are incorrect.")
        return None

    def setup_pins(self):
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)
        for row in self.rows:
            GPIO.setup(row, GPIO.OUT, initial=GPIO.LOW)
        for col in self.cols:
            GPIO.setup(col, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

    def read_line(self, line):
        GPIO.output(line, GPIO.HIGH)
        characters = []
        for col in self.cols:
            key = self.layout[self.rows.index(line)][self.cols.index(col)]
            if GPIO.input(col) == GPIO.HIGH:
                if key not in self.previous_state or not self.previous_state[key]:
                    characters.append(key)
                    self.previous_state[key] = True
            else:
                self.previous_state[key] = False
        GPIO.output(line, GPIO.LOW)
        return characters

    @staticmethod
    def cleanup():
        GPIO.cleanup()

    def read_input(self, prompt, length, mask_input=False):
        print(prompt, end='', flush=True)
        input_value = ""
        start_time = time.time()
        while True:
            if time.time() - start_time > self.input_timeout:
                print("Input timeout, restarting...")
                return None
            pressed_keys = []
            for row in self.rows:
                pressed_keys += self.read_line(row)
            if pressed_keys:
                key = pressed_keys[0]
                if key == '*':
                    input_value = ""
                    print("\r" + " " * (len(prompt) + length) + "\r" + prompt, end='', flush=True)
                elif key == '#':
                    if len(input_value) > 0:
                        print()
                        return input_value
                    else:
                        print("\r" + prompt + " " * len(input_value), end='', flush=True)
                else:
                    if len(input_value) < length:
                        input_value += key
                        display_value = '*' * len(input_value) if mask_input else input_value
                        print("\r" + prompt + display_value, end='', flush=True)
                start_time = time.time()
            time.sleep(0.1)
        print()
        return input_value

    @staticmethod
    def validate_credentials(uid, pin):
        ref = db.reference('security/account')
        accounts = ref.get()
        for username, details in accounts.items():
            if details['uid'] == uid and details['pincode'] == pin:
                return True
        return False

    def run(self):
        try:
            while True:
                uid = self.read_input("Enter UID (4 digits):", 4)
                if uid is None:
                    continue
                pin = self.read_input("Enter PIN (6 digits):", 6, mask_input=True)
                if pin is None:
                    continue
                if self.validate_credentials(uid, pin):
                    print("Access granted.")
                else:
                    print("Access denied.")
        except KeyboardInterrupt:
            print("\nApplication stopped!")
        finally:
            self.cleanup()

    def test_keypad(self):
        print("Testing keypad...")
        try:
            while True:
                for row in self.rows:
                    keys = self.read_line(row)
                    if keys:
                        print(f"Pressed: {keys}")
                time.sleep(0.1)
        except KeyboardInterrupt:
            print("\nStopping keypad test")
        finally:
            self.cleanup()


if __name__ == "__main__":
    fdb.FirebaseDatabase.get_instance()
    rpi_id = "2"
    try:
        device_info = Keypad.get_device_info(rpi_id)
        if device_info:
            rows, cols = device_info
            keypad = Keypad(rows, cols)
            keypad.run()
        else:
            print("No matching device found or incorrect GPIO settings.")
    except (ValueError, AssertionError):
        print("Invalid RPI_ID or GPIO settings.")
