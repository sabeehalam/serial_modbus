import ustruct
import binascii
from machine import UART, Pin
import array
import time
import gc

# Define Modbus function codes
READ_COILS = const(0x01)
READ_HOLDING_REGISTERS = const(0x03)
READ_INPUT_REGISTERS = const(0x04)
WRITE_SINGLE_COIL = const(0x05)
WRITE_HOLDING_REGISTER = const(0x06)

# Define slave address
SLAVE_ADDRESS =const(0x01)

# Define UART parameters
UART_BAUD_RATE = 9600
UART_DATA_BITS = 8
UART_STOP_BITS = 1
UART_PARITY = None

# Define Modbus RTU Registers
coils = {
    0x00: 321,
    0x01: 123,  # Read-Only Integer
    0x02: 456,  # Read-Write Integer
    0x03: False,  # Read-Write Boolean
}

registers = {
    0x00: 321,
    0x01: 123,  # Read-Only Integer
    0x02: 456,  # Read-Write Integer
    0x03: False,  # Read-Write Boolean
}

holding_registers = {
    0x00: 321,
    0x01: 123,  # Read-Only Integer
    0x02: 456,  # Read-Write Integer
    0x03: True, # Read-Write Boolean
    0x04: 123,  # Read-Only Integer
    0x05: 456,  # Read-Write Integer
    0x06: 123,  # Read-Only Integer
    0x07: 456,  # Read-Write Integer
    0x08: 123,  # Read-Only Integer
    0x09: 456,  # Read-Write Integer
}

input_registers = {
    0x00: 321,
    0x01: 123,  # Read-Only Integer
    0x02: 456,  # Read-Write Integer
    0x03: False,  # Read-Write Boolean
    0x04: 123,  # Read-Only Integer
    0x05: 456,  # Read-Write Integer
    0x06: 123,  # Read-Only Integer
    0x07: 456,  # Read-Write Integer
    0x08: 123,  # Read-Only Integer
    0x09: 456,  # Read-Write Integer
}

#Create a 16-bit CRC calculator for the modbus command 
def crc16(buf):
    crc = 0xFFFF  
    for pos in range(len(buf)):
        crc ^= buf[pos]  # XOR byte into least sig. byte of crc
        
        for i in range(8, 0, -1):  # Loop over each bit
            if crc & 0x0001:  # If the LSB is set
                crc >>= 1  # Shift right and XOR 0xA001
                crc ^= 0xA001
            else:  # Else LSB is not set
                crc >>= 1  # Just shift right 
    return crc

#Convert two bytes to a single 2 byte address
def formDecAddress(high_byte, low_byte):
    address = (high_byte << 8) | low_byte
#     hex_address = hex(address)
    return address

#Swap bytes for CRC 
def reverseCRC(crc):
    crc_low, crc_high = divmod(crc, 0x100)
    print("crc ", crc)
    return ustruct.pack(">BB", crc_high, crc_low)

# Function to handle Modbus requests
def handleRequest(data):
    # Extract function code and register/coil address
    slave_address, function_code, start_register_high, start_register_low, register_count_high, register_count_low, recv_crc_1, recv_crc_2= ustruct.unpack(">BBBBBBBB", data)
#     print("Slave address: ", slave_address)
#     print("function_code: ", function_code)
#     print("start_register high: ", start_register_high)
#     print("start_register low: ", start_register_low)
#     print("register_count high: ", register_count_high)
#     print("register_count low: ", register_count_low)
    
    # Compute the received and expected CRCs
    recv_crc = (hex(formDecAddress(recv_crc_2, recv_crc_1)))[2:]
#     print("Received CRC: ", recv_crc)
    command = bytearray(data[0:6], "utf-16")
    expect_crc = hex(crc16(command))[2:]
#     print("Expected CRC: ", expect_crc)
    
    # Compute the start register address
    start_register = formDecAddress(start_register_high, start_register_low)
#     print("Start Register: ", start_register)
    
    # Compute the number of registers
    register_count = formDecAddress(register_count_high, register_count_low)
#     print("Register Count: ", register_count)
    
    # Check matching CRC
    if(recv_crc != expect_crc):
        return None
    
    # Check slave address
    if slave_address != SLAVE_ADDRESS:
        return None
    
    # Handle read coil request
    if function_code == READ_COILS:
        if not 0 < register_count <= 3:
            raise ValueError('Invalid number of coils')
            return None
        response = ustruct.pack(">BBB", slave_address, function_code, (register_count * 2))
        for i in range(register_count):
            response += ustruct.pack(">B", coils[start_register + i])
            
        # Send Modbus RTU response
        return response

    # Handle read holding register request
    elif function_code == READ_HOLDING_REGISTERS: 
        if not 0 <= register_count <= 9:
            raise ValueError('Invalid number of input registers')
#         response = ustruct.pack(">BBHHB", slave_address, function_code, start_register, register_count, (register_count * 2))
        response = ustruct.pack(">BBB", slave_address, function_code, (register_count * 2))
        for i in range(register_count):
            response += (ustruct.pack(">H", holding_registers[(start_register + i)]))
            print("Value ",i, " : ",hex(holding_registers[start_register + i]))
            
        # Send Modbus RTU response
        return response
    
    # Handle read holding register request
    elif function_code == READ_INPUT_REGISTERS:
        if not 0 < register_count <= 9:
            raise ValueError('Invalid number of input registers')
            return None
        response = ustruct.pack(">BBB", slave_address, function_code, (register_count * 2))
        for i in range(register_count):
            response += (ustruct.pack(">H", input_registers[(start_register + i)]))
            print("Value ",i, " : ",hex(input_registers[start_register + i]))
        
        # Send Modbus RTU response
        return response

    # Handle write single coil request
    elif function_code == WRITE_SINGLE_COIL:
        if not 0 < start_register <= 3:
            raise ValueError('Invalid number of coils')
            return None
        # Extract coil value
        coil_value = data[5] != 0x00
        coils[start_register] = coil_value
        return data[0:6]

    # Handle write single register request
    elif function_code == WRITE_HOLDING_REGISTER:
        # Extract register value
        if not 0 < start_register <= 9:
            raise ValueError('Invalid number of register')
            return None
        register_value = ustruct.unpack(">H", data[4:6])[0]
        print("register_value: ", register_value)
        holding_registers[start_register] = int.from_bytes(ustruct.pack(">H", register_value), 'big')
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
        #Check if there's any data available for reading on UART
        #If available read it
        if uart.any():
            data = uart.read(50)
            #If anything was read from UART, send it to handleRequest()
            if data is not None:
                # Handle request
                response_data = handleRequest(data)
            if response_data is not None:
                # Send response
                crc_rev = crc16(response_data)
                crc = reverseCRC(crc_rev)
                print("crc: ", crc)
                response = bytearray(response_data)
                response.extend(crc)

                print("Response = ", response)
                uart.write(response)
                time.sleep(1)
                gc.collect()
                
except KeyboardInterrupt as e:
    print("No more modbus")

