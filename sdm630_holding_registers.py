"""
SDM630 Holding Register Definitions
All holding registers for SDM630, with metadata from specification.
"""
from dataclasses import dataclass

if __package__ is None or __package__ == '':
    # Running standalone, use absolute imports
    from registers import SDM630Register, SDM630Registers
else:
    # Running as a package (Home Assistant component), use relative imports
    from .registers import SDM630Register, SDM630Registers

@dataclass
class SDM630HoldingRegisters(SDM630Registers):
    registers: list[SDM630Register]

    def __init__(self):
        self.registers = []
        self.write_callback = None
        self._init_registers()

    def set_write_callback(self, callback):
        """Set a callback to be notified when any holding register is written to.
        
        Args:
            callback: Function that takes (register, old_value, new_value) as arguments
        """
        self.write_callback = callback
        # Set the callback for all existing registers
        for register in self.registers:
            register.set_value_change_callback(self.write_callback)

    def _init_registers(self):
        # All holding registers from SDM630 MODBUS Protocol (0-based PDU addresses)
        self.registers.append(SDM630Register(2,  2, "Demand Period", "Minutes", 60.0))          # 0x0002
        self.registers.append(SDM630Register(10, 6, "System Type", "Type", 3))                  # 0x000A
        self.registers.append(SDM630Register(12, 7, "Pulse1 Width", "Milliseconds", 5.0))       # 0x000C
        self.registers.append(SDM630Register(14, 8, "Password Lock", "Boolean", 0.0))           # 0x000E
        self.registers.append(SDM630Register(18, 10, "Network Parity Stop", "Float", 1.0))      # 0x0012 One stop bit and even parity
        self.registers.append(SDM630Register(20, 11, "Network Node", "Float", 1.0))             # 0x0014
        self.registers.append(SDM630Register(22, 12, "Pulse1 Divisor1", "Float", 3.0))          # 0x0016
        self.registers.append(SDM630Register(24, 13, "Password", "Float", 0000))                # 0x0018
        self.registers.append(SDM630Register(28, 15, "Network Baud Rate", "Mode", 2.0))         # 0x001C
        self.registers.append(SDM630Register(86, 44, "Pulse 1 Energy Type", "Source", 4.0))     # 0x0056
        super().__init__(self.registers)
        
        # Set the callback for all registers if it exists
        if self.write_callback:
            for register in self.registers:
                register.set_value_change_callback(self.write_callback)

    def get_by_address(self, address):
        for reg in self.registers:
            if reg.address == address:
                return reg
        return None