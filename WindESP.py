import time
import gc
from machine import Pin, UART, WDT
from umodbus.serial import Serial as ModbusRTUMaster

# === Configuration ===
rtu_pins = (Pin(25), Pin(26))  # Modbus RTU communication pins (RX=25, TX=26)
slave_address = 0x01           # Modbus slave address
addresses_to_read = [0x000]    # Adjust as needed

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

# === Initialize UART for sending to RAK ===
send_uart = UART(1, baudrate=9600, bits=8, parity=None, stop=1, tx=17, rx=16)

# === Initialize Watchdog Timer (60 seconds) ===
wdt = WDT(timeout=60000)

# === Read Raw Registers ===
def read_registers_raw(host, slave_addr, starting_addr):
    try:
        registers = host.read_holding_registers(
            slave_addr=slave_addr,
            starting_addr=starting_addr,
            register_qty=2,
            signed=False
        )
        print(f'Address 0x{starting_addr:04X} raw registers:', registers)
        return registers
    except Exception as e:
        print(f'Error reading address 0x{starting_addr:04X}:', e)
        return None

# === Send Raw Registers over UART ===
def send_raw_registers(uart, addr, regs):
    try:
        packet = f'<{addr:04X}:{regs[0]:04X},{regs[1]:04X}>\n'
        uart.write(packet)
        print('Sent to RAK:', packet.strip())
    except Exception as e:
        print('UART sending error:', e)

# === Main Loop ===
while True:
    print('\n--- Starting new reading cycle ---')

    for addr in addresses_to_read:
        regs = read_registers_raw(modbus_uart, slave_address, addr)
        if regs:
            send_raw_registers(send_uart, addr, regs)

    gc.collect()
    print("Free memory:", gc.mem_free())
    wdt.feed()

    for _ in range(10):  # 10s delay
        time.sleep(1)
        wdt.feed()
