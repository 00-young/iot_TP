import time
from collections import Counter

import cv2
from ultralytics import YOLO
from picamera2 import Picamera2
from gpiozero import DistanceSensor
import board
import adafruit_dht

from lcd_control import show_message, clear

from servo_control import open_lid
# LED is not wired up yet. Uncomment when connected.
# Suggested pins:
#   LED (CAN_METAL): GPIO17
#   LED (PLASTIC):   GPIO27
#   LED (PAPER):     GPIO13
# from led_control import light_up, all_off

MODEL_PATH = "best.pt"
CONF_THRESHOLD = 0.5
VOTE_ROUNDS = 5
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

    sensor = DistanceSensor(echo=ECHO_PIN, trigger=TRIGGER_PIN, max_distance=4)

    dht = None
    dht_failed = False
    if DHT_PIN is None:
        dht_failed = True
        print("온습도 센서 인식 못함!")
    else:
        try:
            dht = adafruit_dht.DHT11(DHT_PIN)
        except Exception:
            dht_failed = True
            print("온습도 센서 인식 못함!")

    picam2 = Picamera2()
    config = picam2.create_preview_configuration(
        main={"format": "RGB888", "size": (640, 480)}
    )
    picam2.configure(config)
    picam2.start()
    time.sleep(1)

    show_message("System Ready")
    print("[INFO] System ready. Press Ctrl+C to stop.")

    last_env_check = 0

    try:
        while True:
            dist_cm = sensor.distance * 100

            if dist_cm <= PROXIMITY_THRESHOLD_CM:
                print(f"[PROXIMITY] Object detected at {dist_cm:.1f} cm -> running YOLO")
                show_message("Scanning...")

                def capture():
                    f = picam2.capture_array()
                    return cv2.cvtColor(f, cv2.COLOR_RGB2BGR)

                result = classifier.classify_with_voting(capture)

                if result is not None:
                    print(
                        f"[DETECT] raw={result['raw_class_name']} -> "
                        f"{result['class_name']} (conf={result['confidence']:.2f})"
                    )

                    line2 = result["reminder"] if result["reminder"] else f"Open {result['class_name']} Lid"
                    show_message(result["message"], line2)

                    # Servo actuation
                    if result["class_name"] in ("CAN_METAL", "PLASTIC"):
                        open_lid(result["class_name"])

                    # LED (not wired yet)
                    # if result["class_name"] in ("CAN_METAL", "PLASTIC"):
                    #     light_up(result["class_name"])
                    #     all_off()
                    # elif result["class_name"] == "PAPER":
                    #     light_up("PAPER")
                    #     time.sleep(2)
                    #     all_off()

                    time.sleep(2)
                    show_message("System Ready")
                else:
                    print("[INFO] No object detected.")
                    show_message("No object", "detected")
                    time.sleep(1)
                    show_message("System Ready")

                time.sleep(1)

            else:
                if not dht_failed:
                    now = time.time()
                    if now - last_env_check >= DHT_INTERVAL:
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
        if dht is not None:
            dht.exit()


if __name__ == "__main__":
    main()
