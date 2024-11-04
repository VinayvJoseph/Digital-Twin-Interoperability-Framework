import os
import time
import pytz
from datetime import datetime
from threading import Timer
from picamera2 import Picamera2
from picamera2.encoders import H264Encoder

from firebase_admin import storage
import firebase_database as fdb


def upload_video_to_firebase(local_file_path, storage_file_path):
    bucket = storage.bucket()
    blob = bucket.blob(storage_file_path)
    blob.upload_from_filename(local_file_path)
    print(f"Uploaded {local_file_path} to Firebase Storage at {storage_file_path}.")
    # os.remove(local_file_path)


def convert_to_mp4(h264_path, mp4_path):
    command = f'ffmpeg -i {h264_path} -c:v copy -c:a copy {mp4_path}'
    os.system(command)
    os.remove(h264_path)


def record_video_segment():
    current_time = datetime.now(amsterdam).strftime("%Y%m%d_%H%M%S")
    print(current_time)
    local_h264_path = f'/home/pi/Videos/{current_time}.h264'
    local_mp4_path = f'/home/pi/Videos/{current_time}.mp4'
    storage_path = f'remote/security/{device_id}/{current_time}.mp4'

    # 开始录制一个新的视频片段
    picam2.start_recording(encoder, local_h264_path)
    time.sleep(300)
    picam2.stop_recording()

    convert_to_mp4(local_h264_path, local_mp4_path)

    # 上传视频到 Firebase
    upload_video_to_firebase(local_mp4_path, storage_path)

    # 安排下一个录制
    Timer(0, record_video_segment).start()


# 启动定时录制任务
fdb.FirebaseDatabase.get_instance()
amsterdam = pytz.timezone('Europe/Amsterdam')
device_id = "device_security_0002"
picam2 = Picamera2()
video_config = picam2.create_video_configuration(main={"format": 'XRGB8888', "size": (640, 480)})
picam2.configure(video_config)
encoder = H264Encoder(bitrate=1000000)
picam2.start()

record_video_segment()
