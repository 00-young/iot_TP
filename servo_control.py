# servo_control.py
import time
import threading
from gpiozero import AngularServo

import led_control   # LED 병렬 제어용

# 서보 GPIO 핀 (BCM)
SERVO_PINS = {
    "CAN_METAL": 5,
    "PLASTIC":   6,
}

SERVO_ANGLES = {
    "CAN_METAL": {"open": 60, "closed": 85},
    "PLASTIC":   {"open": 60, "closed": 85},
}

OPEN_DURATION = 5   # 열림 유지 시간(초)

servos = {}

# import 시 1회: 서보 초기화 (닫힘 위치로 시작 + 떨림 방지 detach)
for _bin, _pin in SERVO_PINS.items():
    _closed = SERVO_ANGLES[_bin]["closed"]
    _s = AngularServo(
        _pin,
        initial_angle=_closed,        # 생성 즉시 닫힘 위치로
        min_angle=0, max_angle=180,
        min_pulse_width=0.0005, max_pulse_width=0.0025,
    )
    servos[_bin] = _s
    time.sleep(0.5)
    _s.detach()                       # PWM 끊어 시작 시 떨림 제거


def open_lid(bin_name):
    """뚜껑 열기 → 5초 유지 → 닫기. LED는 병렬 깜빡임. 끝나면 detach."""
    if bin_name not in servos:
        print(f"[SERVO] '{bin_name}' 서보 없는 분류 → 동작 안 함")
        return

    open_angle = SERVO_ANGLES[bin_name]["open"]
    closed_angle = SERVO_ANGLES[bin_name]["closed"]
    servo = servos[bin_name]

    # LED 깜빡임을 별도 스레드로 (서보와 병렬)
    stop_event = threading.Event()
    led_thread = threading.Thread(
        target=led_control.blink_until, args=(bin_name, stop_event), daemon=True,
    )
    led_thread.start()

    # 서보 동작 (바로 각도 이동)
    print(f"[SERVO] {bin_name} 뚜껑 열림")
    servo.angle = open_angle
    time.sleep(OPEN_DURATION)
    servo.angle = closed_angle
    time.sleep(0.5)        # 닫힘 도달 시간
    servo.detach()         # PWM 끊어 떨림 제거

    # LED 정지
    stop_event.set()
    led_thread.join()
    led_control.all_off()
    print(f"[SERVO] {bin_name} 뚜껑 닫힘")