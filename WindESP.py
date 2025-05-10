import time
import struct
import gc
from machine import Pin, UART, WDT
from umodbus.serial import Serial as ModbusRTUMaster

# === Configuration ===
rtu_pins = (Pin(16), Pin(17))  # Modbus RTU communication pins
slave_address = 0x01           # Modbus slave address
addresses_to_read = [0x000] #, 0xBCF, 0xBD1, 0xBF5]

# === Initialize Modbus Master ===
modbus_uart = ModbusRTUMaster(
    baudrate=4800,
    data_bits=8,
    stop_bits=1,
    parity=None,
    pins=rtu_pins,
    ctrl_pin=None,
    uart_id=2
)

# === Initialize UART for sending to another controller ===
send_uart = UART(1, baudrate=9600, bits=8, parity=None, stop=1, tx=25, rx=26)

# === Initialize Watchdog Timer (60 seconds) ===
wdt = WDT(timeout=60000)

# === Function: Read Modbus Float (32-bit) with retries ===
def read_float_from_modbus(host, slave_addr, starting_addr):
    try:
        registers = host.read_holding_registers(
            slave_addr=slave_addr,
            starting_addr=starting_addr,
            register_qty=2,
            signed=False
        )

        print('Address 0x{:04X} raw registers:'.format(starting_addr), registers)

        high_word = registers[0]
        low_word = registers[1]
        combined = (high_word << 16) | low_word

        packed = struct.pack('>I', combined)
        float_value = struct.unpack('>f', packed)[0]
        return float_value

    except Exception as e:
        print('Error reading address 0x{:04X}:'.format(starting_addr), e)
        return None

def read_float_from_modbus_with_retry(host, slave_addr, starting_addr, retries=3):
    for attempt in range(retries):
        value = read_float_from_modbus(host, slave_addr, starting_addr)
        if value is not None:
            return value
        print(f"Retry {attempt+1}/{retries} failed for 0x{starting_addr:04X}")
        time.sleep(0.2)
    print(f"Giving up on 0x{starting_addr:04X}")
    return None

# === Function: Send Floats over UART ===
def send_floats_over_uart(uart, float_dict):
    try:
        packet = '<'
        parts = []
        for addr, value in float_dict.items():
            parts.append('{:04X}:{:.4f}'.format(addr, value))
        packet += ','.join(parts)
        packet += '>\n'
        uart.write(packet)
        print('Sent:', packet.strip())
    except Exception as e:
        print('UART sending error:', e)

# === Main Loop ===
while True:
    print('\n--- Starting new reading cycle ---')

    floats = {}

    for addr in addresses_to_read:
        value = read_float_from_modbus_with_retry(
            modbus_uart, slave_address, addr
        )
        if value is not None:
            floats[addr] = value

    if floats:
        print('All Read Floats:', floats)
        send_floats_over_uart(send_uart, floats)

    # Free unused memory
    gc.collect()
    print("Free memory:", gc.mem_free())

    # Feed watchdog
    wdt.feed()

    # Delay (non-blocking style)
    for _ in range(10):  # total = 10 seconds (adjust as needed)
        time.sleep(1)
        wdt.feed()  # feed periodically even during delay
