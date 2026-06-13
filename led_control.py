
from gpiozero import LED
 
LED_PINS = {
    "PLASTIC": 13,
    "CAN_METAL": 19,
}
 
leds = {bin_name: LED(pin) for bin_name, pin in LED_PINS.items()}
 
 
def light_up(class_name: str, duration: float = 3):
    led = leds.get(class_name)
    if led is None:
        print(f"[LED] No LED configured for class: {class_name}")
        return
 
    for other_name, other_led in leds.items():
        if other_name != class_name:
            other_led.off()
 
    led.on()
    print(f"[LED] {class_name} ON")
 
 
def all_off():
    for led in leds.values():
        led.off()
 
