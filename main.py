import ustruct
import binascii
from machine import UART, Pin
import const
import time

# Define Modbus function codes
READ_COILS = const(0x01)
READ_DISCRETE_INPUTS = const(0x02)
READ_HOLDING_REGISTERS = const(0x03)
READ_INPUT_REGISTERS = const(0x04)
WRITE_SINGLE_COIL = const(0x05)
WRITE_SINGLE_REGISTER = const(0x06)

# Define slave address
SLAVE_ADDRESS =const(0x01)

# Define UART parameters
UART_BAUD_RATE = 9600
UART_DATA_BITS = 8
UART_STOP_BITS = 1
UART_PARITY = None

# Define Modbus registers and coils
registers = bytearray(10)
coils = bytearray(10)

# Define Modbus RTU Registers
coils = {
    0x0001: 123,  # Read-Only Integer
    0x0002: 456,  # Read-Write Integer
    0x0003: False,  # Read-Write Boolean
}

registers = {
    0x01: 123,  # Read-Only Integer
    0x02: 456,  # Read-Write Integer
    0x03: False,  # Read-Write Boolean
}

holding_registers = {
    0x01: 123,  # Read-Only Integer
    0x02: 456,  # Read-Write Integer
    0x03: False,  # Read-Write Boolean
}

input_registers = {
    0x01: 123,  # Read-Only Integer
    0x02: 456,  # Read-Write Integer
    0x03: False,  # Read-Write Boolean
}

PRESET = 0xFFFF
POLYNOMIAL = 0xA001 # bit reverse of 0x8005

def _initial(c):
    crc = 0
    for j in range(8):
        if (crc ^ c) & 0x1:
            crc = (crc >> 1) ^ POLYNOMIAL
        else:
            crc = crc >> 1
        c = c >> 1
    return crc

import array
_tab = array.array("H", [_initial(i) for i in range(256)])

def crc16(str):
    crc = PRESET
    for c in str:
        crc = (crc >> 8) ^ _tab[(crc ^ c) & 0xff]
    return ustruct.pack('<H', crc)

# Function to handle Modbus requests
def handle_request(data):
    
    # Extract function code and register/coil address
    slave_address, function_code, start_register, register_count, recv_crc_1, recv_crc_2= ustruct.unpack(">BBBBBB", data)
    print("Slave address: ", slave_address)
    print("function_code: ", function_code)
    print("start_register: ", start_register)
    print("register_count: ", register_count)

    recv_crc = bytearray([recv_crc_1, recv_crc_2])
    print("recv_crc: ", recv_crc)
    command = bytearray(data[0:4], "utf-16")
    expect_crc = crc16(command)
    print("Expected CRC: ", expect_crc)
    
    # Check matching CRC
    if(recv_crc != expect_crc):
        return None
    
    # Check slave address
    if slave_address != SLAVE_ADDRESS:
        return None
    
    # Handle read coil request
    if function_code == READ_COILS:
        response = ustruct.pack(">BB", slave_address, function_code)
        for i in range(register_count):
            response += ustruct.pack(">H", modbus_registers[start_register + i])
        # Send Modbus RTU response
        return response

    # Handle read holding register request
    elif function_code == READ_HOLDING_REGISTERS:
        response = ustruct.pack(">BB", slave_address, function_code)
        for i in range(register_count):
            response += ustruct.pack(">H", holding_registers[start_register + i])
        # Send Modbus RTU response
        return response
    
        # Handle read holding register request
    elif function_code == READ_INPUT_REGISTERS:
        response = ustruct.pack(">BB", slave_address, function_code)
        for i in range(register_count):
            response += ustruct.pack(">H", input_registers[start_register + i])
        # Send Modbus RTU response
        return response

    # Handle write single coil request
    elif function_code == WRITE_SINGLE_COIL:
        # Extract coil value
        coil_value = data[5] != 0x00
        coils[start_register] = coil_value
        return data[0:6]

    # Handle write single register request
    elif function_code == WRITE_SINGLE_REGISTER:
        # Extract register value
        register_value = ustruct.unpack(">H", data[4:6])[0]
        registers[2 * start_register:2 * (start_register + 1)] = ustruct.pack(">H", register_value)
        return data[0:6]

    # Handle write multiple coils request
    elif function_code == WRITE_MULTIPLE_COILS:
        # Extract coils
        coil_count = register_count
        coil_data = data[7:]
        for i in range(coil_count):
            coils[start_register + i] = (coil_data[i // 8] >> (i % 8)) & 0x01
        return data[0:6]

    # Handle write multiple registers request
    elif function_code == WRITE_MULTIPLE_REGISTERS:
        # Extract registers
        register_data[7:]
    for i in range(register_count):
        value = register_data[2 * i:2 * (i + 1)]
        registers[2 * (start_register + i):2 * (start_register + i + 1)] = value
        return data[0:6]

    # Unsupported function code
    else:
        return None
try:
    # Initialize UART
    uart = UART(1, baudrate=UART_BAUD_RATE)
    uart.init(baudrate=UART_BAUD_RATE, bits=UART_DATA_BITS,
            stop=UART_STOP_BITS, parity=UART_PARITY)
    while True:
        # Wait for Modbus request
        response_data = 0
        data = uart.read(256)
        if data is not None:
            # Handle request
            response_data = handle_request(data)
        if response_data is not None:
            # Send response
            response = bytearray(response_data)
            uart.write(response)
            time.sleep(1)
except KeyboardInterrupt as e:
    print("No more modbus")



