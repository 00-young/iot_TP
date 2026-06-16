import time
from collections import Counter

from ultralytics import YOLO
from picamera2 import Picamera2
from gpiozero import DistanceSensor

import temperature                       # 저전력 온습도 모듈 (전원 게이팅)
from lcd_control import show_message, clear
from servo_control import open_lid
from led_control import all_off

# ---------------------- 설정 ----------------------
MODEL_PATH = "best.pt"
CONF_THRESHOLD = 0.5
VOTE_ROUNDS = 3
VOTE_INTERVAL = 0.3

PROXIMITY_THRESHOLD_CM = 30
TRIGGER_PIN = 23
ECHO_PIN = 24

CAMERA_WARMUP = 1.0   # 카메라 켠 뒤 노출/화이트밸런스 안정화 시간(초)

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

BIN_LOCATION = {
    "CAN_METAL": "--->>",
    "PLASTIC":   "<<---",
}

LABEL_REMINDER = {
    "pet_with_label": "Remove label!",
    "pet_no_label": None,
    "can": None,
    "paper": None,
}


# ---------------------- 분류기 ----------------------
class WasteClassifier:
    def __init__(self, model_path: str = MODEL_PATH, conf: float = CONF_THRESHOLD):
        print(f"[INFO] Loading model from {model_path} ...")
        self.model = YOLO(model_path)
        self.conf = conf
        print(f"[INFO] Model loaded. Classes: {self.model.names}")

    def classify_frame(self, frame):
        results = self.model.predict(source=frame, conf=self.conf, verbose=False)

        if len(results) == 0 or results[0].boxes is None or  len(results[0].boxes) == 0:
            return None

        boxes = results[0].boxes
        best_idx = boxes.conf.argmax().item()

        class_id = int(boxes.cls[best_idx].item())
        confidence = float(boxes.conf[best_idx].item())

        raw_class_name = self.model.names[class_id]
        class_name = CLASS_TO_BIN.get(raw_class_name, "GENERAL_WASTE")
        message = BIN_GUIDE_MESSAGE.get(class_name, "Unknown")
        reminder = LABEL_REMINDER.get(raw_class_name)
        location = BIN_LOCATION.get(class_name, "")

        return {
            "raw_class_name": raw_class_name,
            "class_name": class_name,
            "confidence": confidence,
            "message": message,
            "reminder": reminder,
            "location": location,
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


# ---------------------- 메인 ----------------------
def main():
    classifier = WasteClassifier()

    # 카메라: 설정만 해두고 '시작은 안 함' (트리거 시에만 켬)
    picam2 = Picamera2()
    config = picam2.create_preview_configuration(
        main={"size": (640, 480), "format": "RGB888"}
    )
    picam2.configure(config)
    camera_on = False

    # 거리 센서 (HC-SR04)
    sensor = DistanceSensor(echo=ECHO_PIN, trigger=TRIGGER_PIN, max_distance=2.0)

    # 온습도 모니터링 시작 (별도 스레드 + 측정 외엔 센서 전원 OFF)
    temperature.start()

    def capture_func():
        frame = picam2.capture_array()
        if frame.ndim == 3 and frame.shape[2] == 4:
            frame = frame[:, :, :3]   # 알파(X) 채널 제거 -> 3채널
        return frame

    print("[INFO] System ready. Waiting for objects...")
    show_message("Ready")

    try:
        while True:
            distance_cm = sensor.distance * 100  # m -> cm

            # --- 물체 감지되면: 카메라 ON -> 분류 -> 카메라 OFF ---
            if distance_cm <= PROXIMITY_THRESHOLD_CM:
                print(f"[INFO] Object detected at {distance_cm:.1f} cm")
                show_message("Detecting...")

                # 카메라 ON
                picam2.start()
                camera_on = True
                time.sleep(CAMERA_WARMUP)   # 노출/화이트밸런스 안정화

                result = classifier.classify_with_voting(capture_func)

                # 카메라 OFF (탐지 끝나면 바로 끔)
                picam2.stop()
                camera_on = False

                if result is not None:
                    print(f"[RESULT] {result['raw_class_name']} -> "
                          f"{result['class_name']} ({result['confidence']:.2f})")

                    if result["reminder"]:
                        show_message(result["reminder"])
                        time.sleep(2)

                    # 1줄: 종류 / 2줄: 배출 위치
                    location_line = f" {result['location']}" if result["location"] else ""
                    show_message(result["message"], location_line)
                    open_lid(result["class_name"])   # 서보 + LED 병렬
                else:
                    print("[INFO] Could not classify.")
                    show_message("Try again")
                    time.sleep(1)

                clear()
                time.sleep(1)   # 연속 트리거 방지

            time.sleep(0.2)     # 폴링 간격 (카메라 꺼져 있어 자주 봐도 부담 적음)

    except KeyboardInterrupt:
        print("\n[INFO] Stopped by user.")
    finally:
        if camera_on:
            picam2.stop()
        temperature.stop()
        clear()
        all_off()


if __name__ == "__main__":
    main()