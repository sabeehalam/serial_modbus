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
    0x00: (0b00110010), #Coils 0-7
    0x01: (0b10110000), #Coils 8-15
    0x02: (0b10111011), #Coils 16-23
    0x03: (0b10111100), #Coils 24-31
    0x04: (0b10111111)  #Coils 32-39
    }

coil_single = 0b00000011
discrete_inputs_single = 0b00000011

discrete_inputs = {
    0x00: (0b11110001), #Coils 0-7
#     0x01: (0b10110000), #Coils 8-15
#     0x02: (0b10111011), #Coils 16-23
#     0x03: (0b10111100), #Coils 24-31
#     0x04: (0b10111111)  #Coils 32-39
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

REG_LENGTHS = {
    0x01: len(coils),
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
#     print("crc ordered", crc)
    return ustruct.pack(">BB", crc_high, crc_low)

#check whether a bit is set or not
def isSet(x, n):
    return x & 2 ** n != 0 
    # a more bitwise- and performance-friendly version:
    return x & 1 << n != 0

#Validate the command from master
def validateResponse(data):
    #Print received command
    print("Command: ", data[0:7]) 
    
# #     print and check
#     print("Slave Address: ", slave_address)
#     print("function_code: ", function_code)
#     print("start_register_high: ", start_register_high)
#     print("start_register_low: ", start_register_low)
#     print("value or count high: ", register_count_high)
#     print("value or count low: ", register_count_low)
#     print("recv_crc_1: ", recv_crc_1)
#     print("recv_crc_2: ", recv_crc_2)
    
    # Compute the received and expected CRCs
    recv_crc = (hex(formDecAddress(data[7], data[6])))[2:] #extract crc from command
    command = bytearray(data[0:6], "utf-16") # Convert command to bytearray
    expect_crc = hex(crc16(command))[2:] # Calculate crc from command
    print(recv_crc, " vs ", expect_crc) # Compare both CRCs
    
    # Compute the start register address
    start_register = formDecAddress(data[2], data[3])

    # Check slave address
    if data[0] != SLAVE_ADDRESS:
        print("Slave error called")
        resp = create_exception_resp(data, SLAVE_ERROR)
        return resp
    
    # Check matching CRC
    if(recv_crc != expect_crc):
        print("CRC isn't matching")
        resp = create_exception_resp(data, CRC_ERROR)
        return resp
    
    # Check function code    
    if not (1 <= data[1] < 7):
        print("Wrong function code: ", data[1])
        resp = create_exception_resp(data, ILLEGAL_FUNCTION)
        return resp
    
    register_length = REG_LENGTHS[data[1]]
        
    if not (0 <= start_register <= register_length):
        print("Wrong starting address")
        resp = create_exception_resp(data, ILLEGAL_ADDRESS)
        return resp
    
    # Check function code and validate accordingly
    if(data[1] == 0x01 or data[1] == 0x02):
        return None

    # Check function code and validate accordingly
    if(data[1] == 0x03 or data[1] == 0x04):
        register_count = formDecAddress(data[4], data[5])
        if not (0 <= register_count and (register_count + start_register) <= register_length):
            print("Wrong register count")
            resp = create_exception_resp(data, ILLEGAL_ADDRESS)
            return resp
        return None
    
    # Check function code and validate accordingly    
    if(data[1] == 0x05 or data[1] == 0x06):
        values = formDecAddress(data[4], data[5])    
        if not (values >= 0):
            print("Wrong value impended")
            resp = create_exception_resp(data, ILLEGAL_ADDRESS)
            return resp
        return None
    
    else: return None

# Function to handle Modbus requests
def handleRequest(data):
    global coil_single
    global discrete_input_single
    
    # Unpack slave address and function code from command
    slave_address, function_code = ustruct.unpack(">BB", data[0:2])
    
    if(function_code == 0x01 or function_code == 0x02):
        start_coil_high, start_coil_low, coil_count_high, coil_count_low, recv_crc_1, recv_crc_2 = ustruct.unpack(">BBBBBB", data[2:8])
        start_coil = formDecAddress(start_coil_high, start_coil_low) # Compute the start register address
        coil_count = formDecAddress(coil_count_high, coil_count_low)
    
    # Unpack register address and register count or value and crc for reading registers
    if(function_code == 0x03 or function_code == 0x04):
        start_register_high, start_register_low, register_count_high, register_count_low, recv_crc_1, recv_crc_2 = ustruct.unpack(">BBBBBB", data[2:8])
        start_register = formDecAddress(start_register_high, start_register_low) # Compute the start register address
        register_count = formDecAddress(register_count_high, register_count_low)
        
    # Unpack register address and register count or value and crc
    if(function_code == 0x05 or function_code == 0x06):
        start_register_high, start_register_low, value_high, value_low, recv_crc_1, recv_crc_2 = ustruct.unpack(">BBBBBB", data[2:8])
        start_register = formDecAddress(start_register_high, start_register_low) # Compute the start register address
        values = formDecAddress(value_high, value_low)
        
    # Handle read coil request
    if function_code == READ_COILS:
        response = ustruct.pack(">BBB", slave_address, function_code, coil_count) #Coil count is either 1 or 2 for our case
        coil_values = 0b00
        for bit_index in range(coil_count):
            if isSet(coil_single, bit_index):
                coil_values += 2 ** bit_index
        response += ustruct.pack(">B", coil_values)        
        # Send Modbus RTU response
        return response
    
    # Handle read discrete inputs request
    if function_code == READ_DISCRETE_INPUTS:
        response = ustruct.pack(">BBB", slave_address, function_code, coil_count) #Coil count is either 1 or 2 for our case
        discrete_input_values = 0b00
        for bit_index in range(coil_count):
            if isSet(discrete_input_single, bit_index):
                discrete_input_values += 2 ** bit_index
        response += ustruct.pack(">B", coil_values)      
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
        mask = 1 << start_register
        # Extract coil value
        print("Coil value: ", values)
        if values:
            coil_single | values
        else:
            coil_single & values
        response = ustruct.pack(">BBBB", slave_address, function_code, start_register, values)
        # Send Modbus RTU response
        return response

    # Handle write single register request
    elif function_code == WRITE_HOLDING_REGISTER:
        # Extract register value
        holding_registers[start_register] = int.from_bytes(ustruct.pack(">H", values), 'big')
        response = ustruct.pack(">BBBB", slave_address, function_code, start_register, values)
        # Send Modbus RTU response
        return response

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
            #If anything was read from UART, validate and parse it from validateResponse() and send it to handleRequest()
            if data is not None:
                # Handle request
                response = validateResponse(data)
                # Extract response for command from registers in read case and edit registers in write case
                if response is None:
                    response_data = handleRequest(data)
                    crc = reverseCRC(crc16(response_data))
                    response = bytearray(response_data)
                    response.extend(crc)
                    print("Response = ", response)
                    uart.write(response)
                    gc.collect()
                
                else:
                    crc_rev = crc16(response)
                    crc = reverseCRC(crc_rev)
                    print("crc: ", crc)
                    response_bytes = bytearray(response)
                    response_bytes.extend(crc)
                    print("Response = ", response_bytes)
                    uart.write(response_bytes)
                    response = None
                    gc.collect()
                
except KeyboardInterrupt as e:
    print("No more modbus")

