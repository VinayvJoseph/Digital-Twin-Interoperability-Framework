from flask import Flask, Response, stream_with_context
from picamera2 import Picamera2
from picamera2.encoders import H264Encoder
import cv2
import os
import time
import pytz
from datetime import datetime
from threading import Thread, Timer, Lock
import firebase_admin
from firebase_admin import credentials, storage
import firebase_database as fdb
from firebase_admin import db
import socket

app = Flask(__name__)
client_count = 0
client_lock = Lock()
recording = False
picam2 = Picamera2()
encoder = H264Encoder(bitrate=10000000)

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

def generate_frames():
    while True:
        frame = picam2.capture_array()
        ret, buffer = cv2.imencode('.jpg', frame)
        frame = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

@app.route('/video_feed')
def video_feed():
    global client_count
    with client_lock:
        client_count += 1
    try:
        return Response(stream_with_context(generate_frames()), mimetype='multipart/x-mixed-replace; boundary=frame')
    finally:
        with client_lock:
            client_count -= 1
            if client_count == 0:
                stop_streaming()

def stop_streaming():
    global recording
    if not recording:
        print("No client connected, switching back to recording mode.")
        picam2.stop()
        start_recording()

def upload_video_to_firebase(local_file_path, storage_file_path):
    bucket = storage.bucket()
    blob = bucket.blob(storage_file_path)
    blob.upload_from_filename(local_file_path)
    print(f"Uploaded {local_file_path} to Firebase Storage at {storage_file_path}.")
    os.remove(local_file_path)

def convert_to_mp4(h264_path, mp4_path):
    command = f'ffmpeg -i {h264_path} -c:v copy -c:a copy {mp4_path}'
    os.system(command)
    os.remove(h264_path)

def record_video_segment():
    global recording
    while True:
        with client_lock:
            if client_count > 0:
                if recording:
                    print("Client connected, stopping recording and switching to streaming mode.")
                    picam2.stop_recording()
                    recording = False
                print("Client connected, streaming mode active.")
                picam2.configure(stream_config)
                picam2.start()
                while client_count > 0:
                    time.sleep(1)
                stop_streaming()
            else:
                if not recording:
                    start_recording()

def start_recording():
    global recording
    current_time = datetime.now(amsterdam).strftime("%Y%m%d_%H%M%S")
    print(current_time)
    local_h264_path = f'/home/pi/Videos/{current_time}.h264'
    local_mp4_path = f'/home/pi/Videos/{current_time}.mp4'
    storage_path = f'remote/security/{device_id}/{current_time}.mp4'

    # Configure and start recording
    picam2.configure(video_config)
    picam2.start_recording(encoder, local_h264_path)
    recording = True
    time.sleep(300)
    picam2.stop_recording()
    recording = False

    convert_to_mp4(local_h264_path, local_mp4_path)
    upload_video_to_firebase(local_mp4_path, storage_path)

def start_flask_app():
    app.run(host='0.0.0.0', port=3333)

amsterdam = pytz.timezone('Europe/Amsterdam')
device_id = "device_security_0002"

fdb.FirebaseDatabase.get_instance()
update_ip()

# Configuration for streaming and recording
stream_config = picam2.create_preview_configuration(main={"format": 'XRGB8888', "size": (640, 480)})
video_config = picam2.create_video_configuration(main={"format": 'XRGB8888', "size": (640, 480)})

# Start the Flask app in a separate thread
flask_thread = Thread(target=start_flask_app)
flask_thread.start()

# Start the video recording or streaming task in the main thread or another thread
recording_thread = Thread(target=record_video_segment)
recording_thread.start()
