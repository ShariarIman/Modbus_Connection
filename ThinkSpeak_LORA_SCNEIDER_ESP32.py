import time
import gc
import struct
import network
import urequests
from machine import Pin, UART, WDT
from umodbus.serial import Serial as ModbusRTUMaster

# === Configuration ===
SSID = 'RnD'
PASSWORD = 'Arif0110@'
THINGSPEAK_API_KEY = 'JYHYYK6E34F5MBMH'

rtu_pins = (Pin(16), Pin(17))  # Modbus RTU (RX=16, TX=17)
slave_address = 0x01
addresses_to_read = [0xBCD, 0xBCF, 0xBD1, 0xBF5]

# === Watchdog Timer ===
wdt = WDT(timeout=60000)

# === Wi-Fi Setup ===
def connect_wifi(ssid, password):
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    while not wlan.isconnected():
        print('Connecting to WiFi...')
        wlan.connect(ssid, password)
        timeout = time.time() + 15  # 15 seconds timeout
        while not wlan.isconnected() and time.time() < timeout:
            time.sleep(1)
        if not wlan.isconnected():
            print("WiFi connection failed, retrying...")
        else:
            break
    if wlan.isconnected():
        print('WiFi connected:', wlan.ifconfig())
    else:
        print("Failed to connect to WiFi after retries.")

# === Check and Reconnect Wi-Fi ===
def ensure_wifi_connected():
    wlan = network.WLAN(network.STA_IF)
    if not wlan.isconnected():
        print("WiFi lost. Reconnecting...")
        connect_wifi(SSID, PASSWORD)

# === ThingSpeak Sender ===
def send_all_to_thingspeak(floats):
    try:
        gc.collect()
        fields = '&'.join([f'field{i+1}={v:.4f}' for i, v in enumerate(floats)])
        url = f"http://api.thingspeak.com/update?api_key={THINGSPEAK_API_KEY}&{fields}"
        response = urequests.get(url)
        print("ThingSpeak response:", response.text)
        response.close()
    except Exception as e:
        print("ThingSpeak error:", e)

# === Modbus Read (with Retry + Float conversion) ===
def read_float_from_modbus_with_retry(host, slave_addr, starting_addr, retries=3):
    for attempt in range(retries):
        try:
            regs = host.read_holding_registers(
                slave_addr=slave_addr,
                starting_addr=starting_addr,
                register_qty=2,
                signed=False
            )
            print(f'Address 0x{starting_addr:04X} registers:', regs)

            combined = (regs[0] << 16) | regs[1]
            packed = struct.pack('>I', combined)
            float_value = struct.unpack('>f', packed)[0]
            return float_value, regs
        except Exception as e:
            print(f"Error reading 0x{starting_addr:04X} (attempt {attempt+1}):", e)
            time.sleep(0.1)  # brief pause before retry
    print(f"Giving up on 0x{starting_addr:04X}")
    return None, None

# === Send Raw Registers to UART ===
def send_raw_registers(uart, addr, regs):
    try:
        packet = f'<{addr:04X}:{regs[0]:04X},{regs[1]:04X}>\n'
        uart.write(packet)
        print('Sent to UART:', packet.strip())
    except Exception as e:
        print('UART sending error:', e)

# === Hardware Initialization ===
connect_wifi(SSID, PASSWORD)

modbus_uart = ModbusRTUMaster(
    baudrate=19200,
    data_bits=8,
    stop_bits=1,
    parity=None,
    pins=rtu_pins,
    ctrl_pin=None,
    uart_id=2
)

send_uart = UART(1, baudrate=9600, bits=8, parity=None, stop=1, tx=25, rx=26)

# === Timing ===
interval_ms = 30000  # 30 seconds
last_update_ms = time.ticks_ms()

# === Main Loop ===
while True:
    now = time.ticks_ms()

    if time.ticks_diff(now, last_update_ms) >= interval_ms:
        print('\n--- 30s cycle triggered ---')

        ensure_wifi_connected()

        float_values = []
        for addr in addresses_to_read:
            float_val, regs = read_float_from_modbus_with_retry(
                modbus_uart, slave_address, addr
            )
            if regs:
                send_raw_registers(send_uart, addr, regs)
            if float_val is not None:
                float_values.append(float_val)
            else:
                float_values.append(0.0)  # fallback for failed reads

        send_all_to_thingspeak(float_values)

        last_update_ms = now
        gc.collect()
        print("Free memory:", gc.mem_free())

    wdt.feed()
