"""
SDM630 Modbus Protocol Simulator using pymodbus
Implements all input and holding registers as per SDM630 documentation.
"""
from pymodbus.server import StartTcpServer
from pymodbus.datastore import ModbusServerContext, ModbusSparseDataBlock, ModbusSlaveContext
from pymodbus.device import ModbusDeviceIdentification
import struct

# Determine if we're running as a package (Home Assistant component) or standalone
if __package__ is None or __package__ == '':
    # Running standalone, use absolute imports
    from registers import SDM630Registers
    from sdm630_input_registers import SDM630InputRegisters
    from sdm630_holding_registers import SDM630HoldingRegisters
else:
    # Running as a package (Home Assistant component), use relative imports
    from .registers import SDM630Registers
    from .sdm630_input_registers import SDM630InputRegisters
    from .sdm630_holding_registers import SDM630HoldingRegisters

def float_to_regs(value):
    """Convert float to two 16-bit Modbus registers (IEEE 754)"""
    b = struct.pack('>f', value)
    return [int.from_bytes(b[:2], 'big'), int.from_bytes(b[2:], 'big')]

class SDM630DataBlock(ModbusSparseDataBlock):
    def __init__(self, registers : SDM630Registers):
        super().__init__()
        self.registers = registers
        self._float_map_to_regs()

    def _float_map_to_regs(self):
        for register in self.registers.get_all():
            reg_value = float_to_regs(register.get_value())
            reg_address = register.get_address()
            super().setValues(reg_address, reg_value[0])
            super().setValues(reg_address + 1, reg_value[1])

    def set_float(self, address, value):
        self.registers.set_float(address, value)
        self._float_map_to_regs()

    def get_float(self, address):  
        """Get a float value from the register address."""
        return self.registers.get_float(address)

# Use imported SDM630InputRegisters and SDM630HoldingRegisters for register management
holding_data_block = SDM630DataBlock(SDM630HoldingRegisters())
input_data_block = SDM630DataBlock(SDM630InputRegisters())

# Create Modbus server context for input and holding registers
slave_context = ModbusSlaveContext(
    di = ModbusSparseDataBlock({}),
    co = ModbusSparseDataBlock({}),
    hr = holding_data_block,
    ir = input_data_block
)

context = ModbusServerContext(slaves=slave_context, single=True)

# Device identification
identity = ModbusDeviceIdentification()
identity.VendorName = 'Eastron'
identity.ProductCode = 'SDM630'
identity.VendorUrl = 'https://www.eastrongroup.com/'
identity.ProductName = 'SDM630 Modbus Simulator'
identity.ModelName = 'SDM630'
identity.MajorMinorRevision = '1.0'

if __name__ == "__main__":
    print("Starting SDM630 Modbus TCP Simulator...")
    StartTcpServer(context, identity=identity, framer="rtu", address=("0.0.0.0", 5020))
