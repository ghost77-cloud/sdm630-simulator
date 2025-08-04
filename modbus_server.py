"""
SDM630 Modbus Protocol Simulator using pymodbus
Implements all input and holding registers as per SDM630 documentation.
"""
from pymodbus.server import StartTcpServer
from pymodbus.datastore import ModbusServerContext, ModbusSparseDataBlock
from pymodbus.datastore import ModbusSlaveContext
from pymodbus.device import ModbusDeviceIdentification
import struct
import importlib.util
import sys

# Determine if we're running as a package (Home Assistant component) or standalone
if __package__ is None or __package__ == '':
    # Running standalone, use absolute imports
    from sdm630_input_registers import SDM630InputRegisters
    from sdm630_holding_registers import SDM630HoldingRegisters
else:
    # Running as a package (Home Assistant component), use relative imports
    from .sdm630_input_registers import SDM630InputRegisters
    from .sdm630_holding_registers import SDM630HoldingRegisters

SDM630_HOLDING_REGISTERS = {
    # 4X registers: 40003 (2) to 40087 (86), plus special config registers
    # Only even addresses are valid for floating point values
}
for addr in [2, 10, 12, 14, 16, 18, 20, 22, 24, 26, 28, 30, 32, 34, 36, 38, 40, 42, 44, 46, 48, 50, 52, 54, 56, 58, 60, 62, 64, 66, 68, 70, 72, 74, 76, 78, 80, 82, 84, 86]:
    SDM630_HOLDING_REGISTERS[addr] = 0.0

def float_to_regs(value):
    """Convert float to two 16-bit Modbus registers (IEEE 754)"""
    b = struct.pack('>f', value)
    return [int.from_bytes(b[:2], 'big'), int.from_bytes(b[2:], 'big')]

# Helper to manage register values and update them dynamically
class SDM630RegisterManager:
    def __init__(self, reg_map):
        self.reg_map = reg_map

    def set_float(self, addr, value):
        """Set a float value at Modbus register address (even only)"""
        self.reg_map[addr] = value

    def get_float(self, addr):
        return self.reg_map.get(addr, 0.0)

    def get_all(self):
        return self.reg_map

class SDM630DataBlock(ModbusSparseDataBlock):
    def __init__(self, reg_manager):
        self.reg_manager = reg_manager
        regs = self._float_map_to_regs()
        super().__init__(regs)

    def _float_map_to_regs(self):
        regs = {}
        for addr, val in self.reg_manager.get_all().items():
            regs[addr] = float_to_regs(val)[0]
            regs[addr+1] = float_to_regs(val)[1]
        return regs

    def setValues(self, address, values):
        # Optionally allow writing to registers (not typical for input regs)
        for i, v in enumerate(values):
            self.reg_manager.set_float(address + 2*i, v)
        self._update_regs()

    def _update_regs(self):
        # Refresh internal register map from reg_manager
        self.values = self._float_map_to_regs()

# Use imported SDM630InputRegisters and SDM630HoldingRegisters for register management
input_registers_obj = SDM630InputRegisters()
input_reg_manager = SDM630RegisterManager(input_registers_obj.as_dict())
holding_registers_obj = SDM630HoldingRegisters()
holding_reg_manager = SDM630RegisterManager(holding_registers_obj.as_dict())

# Create Modbus server context for input and holding registers
slave_context = ModbusSlaveContext(
    di = ModbusSparseDataBlock({}),
    co = ModbusSparseDataBlock({}),
    hr = SDM630DataBlock(holding_reg_manager),
    ir = SDM630DataBlock(input_reg_manager)
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
