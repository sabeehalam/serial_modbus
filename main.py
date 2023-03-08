import ustruct
from machine import UART, Pin
import array
import time
import gc

# Define Modbus function codes
READ_COILS = const(0x01)
READ_DISCRETE_INPUTS = const(0x02)
READ_HOLDING_REGISTERS = const(0x03)
READ_INPUT_REGISTERS = const(0x04)
WRITE_SINGLE_COIL = const(0x05)
WRITE_HOLDING_REGISTER = const(0x06)

# Define slave address
SLAVE_ADDRESS =const(0x01)

#Define exception codes for errors
EXCEPTION_CODE = const(0x84)  # Exception response offset
ILLEGAL_FUNCTION = const(0x01)
ILLEGAL_ADDRESS = const(0x02)
ILLEGAL_DATA = const(0x03)
SLAVE_ERROR = const(0x04)
CRC_ERROR = const(0x10)

# Define UART parameters
UART_BAUD_RATE = 9600
UART_DATA_BITS = 8
UART_STOP_BITS = 1
UART_PARITY = None

# Define Modbus RTU Registers
coils = {
    0x00: int('0b1011001', 2),
    0x01: int('0b1011000', 2),
    0x02: int('0b1011010', 2),
    0x03: int('0b1011000', 2),
    0x04: int('0b1011100', 2)
    }

discrete_inputs = {
    0x00: int('0b1111000', 2),
    0x01: int('0b1011000', 2),
    0x02: int('0b1011101', 2),
    0x03: int('0b1011110', 2),
    0x04: int('0b1011111', 2)
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

REG_LENGTHS = { 0x01: len(coils),
                0x02: len(discrete_inputs),
                0x03: len(holding_registers),
                0x04: len(input_registers),
                0x05: len(coils),
                0x06: len(holding_registers) 
                }

def create_exception_resp(request, exc_code):
    # Build Modbus exception response
    resp = ustruct.pack(">BBB", request[0], EXCEPTION_CODE, exc_code)
    return resp

#Validate the command from master
def validateResponse(data):
    slave_address, function_code, start_register_high, start_register_low, register_count_high, register_count_low, recv_crc_1, recv_crc_2= ustruct.unpack(">BBBBBBBB", data)
    
    # Compute the received and expected CRCs
    recv_crc = (hex(formDecAddress(recv_crc_2, recv_crc_1)))[2:]
    command = bytearray(data[0:6], "utf-16")
    expect_crc = hex(crc16(command))[2:]
    
    # Compute the start register address
    start_register = formDecAddress(start_register_high, start_register_low)
    
    # Compute the number of registers
    register_count = formDecAddress(register_count_high, register_count_low)

    # Check slave address
    if slave_address != SLAVE_ADDRESS:
        print("Slave error called")
        resp = create_exception_resp(data, SLAVE_ERROR)
        return resp
    
    # Check matching CRC
    if(recv_crc != expect_crc):
        print("CRC isn't matching")
        resp = create_exception_resp(data, CRC_ERROR)
        return resp
       
    if not (1 <= function_code < 7):
        print("Wrong function code: ", function_code)
        resp = create_exception_resp(data, ILLEGAL_FUNCTION)
        return resp
    
    register_length = REG_LENGTHS[function_code]
        
    if not (0 <= start_register <= register_length):
        print("Wrong starting address")
        resp = create_exception_resp(data, ILLEGAL_ADDRESS)
        return resp
    
    if not (0 <= register_count <= register_length - start_register):
        print("Wrong register count")
        resp = create_exception_resp(data, ILLEGAL_ADDRESS)
        return resp
    
    else: return None
    
    
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
    return address

#Swap bytes for CRC 
def reverseCRC(crc):
    crc_low, crc_high = divmod(crc, 0x100)
    print("crc ordered", crc)
    return ustruct.pack(">BB", crc_high, crc_low)

# Function to handle Modbus requests
def handleRequest(data):
    # Extract function code and register/coil address
    slave_address, function_code, start_register_high, start_register_low, register_count_high, register_count_low, recv_crc_1, recv_crc_2= ustruct.unpack(">BBBBBBBB", data)
    
    # Compute the start register address
    start_register = formDecAddress(start_register_high, start_register_low)
    
    # Compute the number of registers
    register_count = formDecAddress(register_count_high, register_count_low)
    
    # Handle read coil request
    if function_code == READ_COILS:
        response = ustruct.pack(">BBB", slave_address, function_code, (register_count * 2))
        for i in range(register_count):
            response += ustruct.pack(">H", coils[start_register + i])        
        # Send Modbus RTU response
        return response

    # Handle read holding register request
    elif function_code == READ_HOLDING_REGISTERS: 
        response = ustruct.pack(">BBB", slave_address, function_code, (register_count * 2))
        for i in range(register_count):
            response += (ustruct.pack(">H", holding_registers[(start_register + i)]))      
        # Send Modbus RTU response
        return response
    
    # Handle read holding register request
    elif function_code == READ_INPUT_REGISTERS:
        response = ustruct.pack(">BBB", slave_address, function_code, (register_count * 2))
        for i in range(register_count):
            response += (ustruct.pack(">H", input_registers[(start_register + i)]))
        
        # Send Modbus RTU response
        return response

    # Handle write single coil request
    elif function_code == WRITE_SINGLE_COIL:
        # Extract coil value
        coil_value = data[5] != 0x00
        coils[start_register] = coil_value
        return data[0:6]

    # Handle write single register request
    elif function_code == WRITE_HOLDING_REGISTER:
        # Extract register value
        register_value = ustruct.unpack(">H", data[4:6])[0]
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
            data = uart.read(40)
            #If anything was read from UART, send it to handleRequest()
            
            if data is not None:
                # Handle request
                val = validateResponse(data)
                
            if val == None:
                # Send response
                response_data = handleRequest(data)
                crc_rev = crc16(response_data)
                crc = reverseCRC(crc_rev)
                response = bytearray(response_data)
                response.extend(crc)
                print("Response = ", response)
                uart.write(response)
                val = None
                gc.collect()
                
            else:
                crc_rev = crc16(val)
                crc = reverseCRC(crc_rev)
                print("crc: ", crc)
                response = bytearray(val)
                response.extend(crc)
                print("Response = ", response)
                uart.write(response)
                val = None
                gc.collect()
                
except KeyboardInterrupt as e:
    print("No more modbus")

