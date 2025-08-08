"""
SDM630 Modbus Protocol Simulator using pymodbus
Implements all input and holding registers as per SDM630 documentation.
"""
from pymodbus.server import StartTcpServer
from pymodbus.datastore import ModbusServerContext, ModbusSparseDataBlock, ModbusSlaveContext
from pymodbus.device import ModbusDeviceIdentification
import struct
import logging

# Determine if we're running as a package (Home Assistant component) or standalone
if __package__ is None or __package__ == '':
    # Running standalone, use absolute imports
    from registers import SDM630Registers, SDM630Register
    from sdm630_input_registers import SDM630InputRegisters
    from sdm630_holding_registers import SDM630HoldingRegisters
else:
    # Running as a package (Home Assistant component), use relative imports
    from .registers import SDM630Registers, SDM630Register
    from .sdm630_input_registers import SDM630InputRegisters
    from .sdm630_holding_registers import SDM630HoldingRegisters

_LOGGER = logging.getLogger(__name__)

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

    def setValues(self, address, value):
        """Override the setValues method from ModbusSparseDataBlock to handle writes from Modbus clients"""
        # First call the parent class setValues to update the internal storage
        super().setValues(address, value)
        
        # Check if this is the first or second register of a float pair
        if address % 2 == 1:  # Odd address - potential start of float
            # Try to get both registers to form the float
            reg1 = self.getValues(address, 1)[0]
            reg2 = self.getValues(address + 1, 1)[0]
            # Convert the two registers back to float
            try:
                float_value = struct.unpack('>f', struct.pack('>HH', reg1, reg2))[0]
                # Update our register object with the new float value
                self.registers.set_float(address, float_value)
            except (struct.error, IndexError):
                pass  # Handle case where second register isn't available yet

    def set_float(self, address, value):
        """Set a float value from our code (not from Modbus client)"""
        self.registers.set_float(address, value)
        self._float_map_to_regs()

    def get_float(self, address):  
        """Get a float value from the register address."""
        return self.registers.get_float(address)

# Use imported SDM630InputRegisters and SDM630HoldingRegisters for register management
holding_registers = SDM630HoldingRegisters()

# Set up callback for holding register writes
def on_holding_register_write(register: SDM630Register, old_value: float, new_value: float):
    _LOGGER.warning(f"Holding register write - Address: {register.address}, Description: {register.description}")
    _LOGGER.warning(f"Old value: {old_value}, New value: {new_value}")

holding_registers.set_write_callback(on_holding_register_write)

holding_data_block = SDM630DataBlock(holding_registers)
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
    _LOGGER.warning(f"Starting SDM630 Modbus TCP Simulator...")
    StartTcpServer(context, identity=identity, framer="rtu", address=("0.0.0.0", 5020))
