from flask import Flask, Response
import socket

from picamera2 import Picamera2, Preview
from picamera2.encoders import H264Encoder

import firebase_database as fdb
from firebase_admin import db


app = Flask(__name__)
picam2 = Picamera2()


def initialize_camera():
    picam2.configure(
        picam2.create_video_configuration(
            main={"format": "XRGB8888", "size": (640, 480)}))
    encoder = H264Encoder(bitrate=1000000)
    picam2.start_encoder(encoder)
    return encoder


encoder = initialize_camera()


@app.route('/video_feed')
def video_feed():
    def gen():
        while True:
            buffer = encoder.get_frame()
            yield (b'--frame\r\n'
                   b'Content-Type: video/h264\r\n\r\n' + buffer + b'\r\n')

    return Response(gen(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')


def get_ip_address():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("8.8.8.8", 80))
    ip = s.getsockname()[0]
    s.close()
    return ip


def update_ip():
    ip_address = get_ip_address()
    devices_ref = db.reference('room/device/security')
    devices = devices_ref.get() or {}
    rpi_id = "3"

    for device_id, details in devices.items():
        if details.get('detailed_type') == 'camera' and details.get('rpi_id') == rpi_id:
            devices_ref.child(device_id).update({'ip_address': ip_address})
            print(f"Updated IP address for device {device_id} to {ip_address}")


if __name__ == '__main__':
    fdb.FirebaseDatabase.get_instance()
    update_ip()

    picam2.start()
    app.run(host='0.0.0.0', port=8000)

