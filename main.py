import time
import threading
from collections import Counter

import cv2
from ultralytics import YOLO
from picamera2 import Picamera2
from gpiozero import DistanceSensor
import board
import adafruit_dht

from lcd_control import show_message, clear

from servo_control import open_lid
from led_control import light_up, all_off

MODEL_PATH = "best.pt"
CONF_THRESHOLD = 0.5
VOTE_ROUNDS = 3
VOTE_INTERVAL = 0.3

PROXIMITY_THRESHOLD_CM = 30
ECHO_PIN = 24
TRIGGER_PIN = 23

DHT_PIN = None
try:
    DHT_PIN = board.D4
except AttributeError:
    try:
        DHT_PIN = board.GPIO4
    except AttributeError:
        DHT_PIN = None

DHT_INTERVAL = 5

CLASS_TO_BIN = {
    "can": "CAN_METAL",
    "pet_with_label": "PLASTIC",
    "pet_no_label": "PLASTIC",
    "paper": "PAPER",
}

BIN_GUIDE_MESSAGE = {
    "CAN_METAL": "Can/Metal",
    "PLASTIC": "Plastic",
    "PAPER": "Paper",
}

LABEL_REMINDER = {
    "pet_with_label": "Remove label!",
    "pet_no_label": None,
    "can": None,
    "paper": None,
}

class WasteClassifier:
    def __init__(self, model_path: str = MODEL_PATH, conf: float = CONF_THRESHOLD):
        print(f"[INFO] Loading model from {model_path} ...")
        self.model = YOLO(model_path)
        self.conf = conf
        print(f"[INFO] Model loaded. Classes: {self.model.names}")

    def classify_frame(self, frame):
        results = self.model.predict(
            source=frame,
            conf=self.conf,
            verbose=False,
        )

        if len(results) == 0 or len(results[0].boxes) == 0:
            return None

        boxes = results[0].boxes
        best_idx = boxes.conf.argmax().item()

        class_id = int(boxes.cls[best_idx].item())
        confidence = float(boxes.conf[best_idx].item())

        raw_class_name = self.model.names[class_id]

        class_name = CLASS_TO_BIN.get(raw_class_name, "GENERAL_WASTE")
        message = BIN_GUIDE_MESSAGE.get(class_name, "Unknown")

        reminder = LABEL_REMINDER.get(raw_class_name)

        return {
            "raw_class_name": raw_class_name,
            "class_name": class_name,
            "confidence": confidence,
            "message": message,
            "reminder": reminder,
        }

    def classify_with_voting(self, capture_func, rounds: int = VOTE_ROUNDS, interval: float = VOTE_INTERVAL):
        votes = []
        last_result_by_class = {}

        for _ in range(rounds):
            frame = capture_func()
            result = self.classify_frame(frame)

            if result is not None:
                votes.append(result["raw_class_name"])
                last_result_by_class[result["raw_class_name"]] = result

            time.sleep(interval)

        if not votes:
            return None

        most_common_class, _ = Counter(votes).most_common(1)[0]
        return last_result_by_class[most_common_class]
    
def main():
    classifier = WasteClassifier()

    # --- 카메라 초기화 ---
    picam2 = Picamera2()
    config = picam2.create_preview_configuration(main={"size": (640, 480),"format":"RGB888"})
    picam2.configure(config)
    picam2.start()
    time.sleep(2)  # 카메라 워밍업

    # --- 거리 센서 (HC-SR04) ---
    sensor = DistanceSensor(echo=ECHO_PIN, trigger=TRIGGER_PIN, max_distance=2.0)

    # --- 온습도 센서 (DHT11) ---
    dht = None
    if DHT_PIN is not None:
        try:
            dht = adafruit_dht.DHT11(DHT_PIN)
        except Exception as e:
            print(f"[WARN] DHT init failed: {e}")
            dht = None

    def capture_func():
        frame = picam2.capture_array()
        if frame.ndim == 3 and frame.shape[2] == 4:
            frame = frame[:, :, :3]   # 알파(X) 채널 제거 -> 3채널
        return frame

    print("[INFO] System ready. Waiting for objects...")
    show_message("Ready")
    last_env_check = 0.0

    try:
        while True:
            distance_cm = sensor.distance * 100  # m -> cm

            # --- 물체 감지되면 분류 시작 ---
            if distance_cm <= PROXIMITY_THRESHOLD_CM:
                print(f"[INFO] Object detected at {distance_cm:.1f} cm")
                show_message("Detecting...")

                result = classifier.classify_with_voting(capture_func)

                if result is not None:
                    print(f"[RESULT] {result['raw_class_name']} -> "
                          f"{result['class_name']} ({result['confidence']:.2f})")

                    # 라벨 제거 안내가 있으면 먼저 보여줌
                    if result["reminder"]:
                        show_message(result["reminder"])
                        time.sleep(2)

                    show_message(result["message"])

                    # 서보 + LED 병렬 동작 (열림 -> 5초 -> 닫힘)
                    open_lid(result["class_name"])
                else:
                    print("[INFO] Could not classify.")
                    show_message("Try again")
                    time.sleep(1)
                clear()
                time.sleep(1)  # 연속 트리거 방지

            # --- 온습도 주기적 체크 ---
            now = time.time()
            if dht is not None and now - last_env_check >= DHT_INTERVAL:
                try:
                    temp = dht.temperature
                    humid = dht.humidity
                    if temp is not None and humid is not None:
                        print(f"[ENV] Temp: {temp}C  Humidity: {humid}%")
                except RuntimeError:
                    pass
                last_env_check = now

            time.sleep(0.5)

    except KeyboardInterrupt:
        print("\n[INFO] Stopped by user.")
    finally:
        picam2.stop()
        clear()
        all_off()
        if dht is not None:
            dht.exit()


if __name__ == "__main__":
    main()

