import time
import threading
from gpiozero import LED

# LED GPIO 핀 (BCM)
LED_PINS = {
    "CAN_METAL": 13,   # 빨강 (캔/금속)
    "PLASTIC":   19,   # 초록 (플라스틱)
}

leds = {name: LED(pin) for name, pin in LED_PINS.items()}


def light_up(bin_name):
    """해당 LED만 솔리드로 켜고 나머지는 끔"""
    all_off()
    if bin_name in leds:
        leds[bin_name].on()


def blink_until(bin_name, stop_event, interval=0.3):
    """stop_event가 set() 될 때까지 깜빡임 (서보와 병렬 실행용 스레드 타깃)"""
    if bin_name not in leds:
        return
    led = leds[bin_name]
    while not stop_event.is_set():
        led.on()
        time.sleep(interval)
        led.off()
        time.sleep(interval)
    led.off()


def all_off():
    for led in leds.values():
        led.off()