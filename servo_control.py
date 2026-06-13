import time
from gpiozero import AngularServo

SERVO_PINS = {
    "CAN_METAL": 5,
    "PLASTIC": 6,
}

SERVO_ANGLES = {
    "CAN_METAL": {"open": 0, "closed": 90},
    "PLASTIC": {"open": 90, "closed": 0},
}

OPEN_DURATION = 3

servos = {}
for bin_name, pin in SERVO_PINS.items():
    servo = AngularServo(
        pin,
        min_angle=0,
        max_angle=180,
        min_pulse_width=0.0005,
        max_pulse_width=0.0025,
    )
    servo.angle = SERVO_ANGLES[bin_name]["closed"]
    time.sleep(0.3)
    servo.detach()
    servos[bin_name] = servo


def open_lid(class_name: str, duration: float = OPEN_DURATION):
    servo = servos.get(class_name)
    angles = SERVO_ANGLES.get(class_name)
    if servo is None or angles is None:
        print(f"[SERVO] No servo configured for class: {class_name}")
        return

    print(f"[SERVO] Opening lid for {class_name}")
    servo.angle = angles["open"]
    time.sleep(duration)
    servo.angle = angles["closed"]
    time.sleep(0.3)
    servo.detach()
    print(f"[SERVO] Closed lid for {class_name}")


if __name__ == "__main__":
    open_lid("CAN_METAL")
    time.sleep(1)
    open_lid("PLASTIC")
