import time
from gpiozero import AngularServo

SERVO_PINS = {
    "CAN_METAL": 5,
    "PLASTIC": 6,
}

OPEN_ANGLE = 90
CLOSED_ANGLE = 0
OPEN_DURATION = 3

servos = {}
for bin_name, pin in SERVO_PINS.items():
    servos[bin_name] = AngularServo(
        pin,
        min_angle=0,
        max_angle=180,
        min_pulse_width=0.0005,
        max_pulse_width=0.0025,
    )
    servos[bin_name].angle = CLOSED_ANGLE


def open_lid(class_name: str, duration: float = OPEN_DURATION):
    servo = servos.get(class_name)
    if servo is None:
        print(f"[SERVO] No servo configured for class: {class_name}")
        return

    print(f"[SERVO] Opening lid for {class_name}")
    servo.angle = OPEN_ANGLE
    time.sleep(duration)
    servo.angle = CLOSED_ANGLE
    print(f"[SERVO] Closed lid for {class_name}")


if __name__ == "__main__":
    open_lid("CAN_METAL")
    time.sleep(1)
    open_lid("PLASTIC")
