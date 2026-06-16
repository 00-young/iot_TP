import time
import threading

import board
import digitalio
import adafruit_dht

# --- 핀 설정 ---
DHT_DATA_PIN = board.D22      # 데이터(S) 핀: GPIO22 (물리 15번)
POWER_PIN = board.D27         # 전원 핀: GPIO27 (물리 13번) -> 센서 VCC에 연결

# --- 동작 설정 ---
READ_INTERVAL = 3            # 콘솔 출력 간격(초)
WARMUP_TIME = 2              # 전원 인가 후 안정화 대기(초, DHT11은 최소 1초 필요)

_thread = None
_stop_event = threading.Event()


def _monitor_loop():
    # 전원 핀을 출력으로 설정, 시작은 OFF
    power = digitalio.DigitalInOut(POWER_PIN)
    power.direction = digitalio.Direction.OUTPUT
    power.value = False

    dht = adafruit_dht.DHT11(DHT_DATA_PIN)

    try:
        while not _stop_event.is_set():
            start = time.time()

            # 1) 센서 전원 ON -> 안정화 대기
            power.value = True
            time.sleep(WARMUP_TIME)

            # 2) 측정 + 콘솔 출력
            try:
                temp = dht.temperature
                humid = dht.humidity
                if temp is not None and humid is not None:
                    print(f"[ENV] 온도: {temp}°C  습도: {humid}%")
                else:
                    print("[ENV] 읽기 실패 (값 없음)")
            except RuntimeError as e:
                # DHT는 가끔 읽기 실패가 정상 -> 다음 주기에 재시도
                print(f"[ENV] 읽기 실패, 재시도: {e.args[0]}")

            # 3) 측정 끝 -> 전원 OFF (대기 중 전력 소비 차단)
            power.value = False

            # 4) 전체 주기를 READ_INTERVAL(3초)에 맞춰 대기
            elapsed = time.time() - start
            _stop_event.wait(max(0, READ_INTERVAL - elapsed))
    finally:
        power.value = False
        dht.exit()
        power.deinit()

def start():
    """백그라운드에서 온습도 모니터링 시작 (main.py에서 호출)."""
    global _thread
    if _thread is not None and _thread.is_alive():
        return
    _stop_event.clear()
    _thread = threading.Thread(target=_monitor_loop, daemon=True)
    _thread.start()
    print("[ENV] 온습도 모니터링 시작 (3초 간격, 측정 외 시간 전원 OFF)")


def stop():
    """온습도 모니터링 종료."""
    _stop_event.set()
    if _thread is not None:
        _thread.join(timeout=READ_INTERVAL + WARMUP_TIME + 1)
    print("[ENV] 온습도 모니터링 종료")


if __name__ == "__main__":
    # 단독 실행: 3초마다 콘솔 출력, Ctrl+C로 종료
    start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        stop()
        print("종료")
