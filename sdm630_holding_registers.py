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
        # All holding registers from SDM630 MODBUS Protocol (1-based PDU addresses)
        self.registers.append(SDM630Register(3,  2, "Demand Period", "Minutes", 60.0))          # 0x0003
        self.registers.append(SDM630Register(11, 6, "System Type", "Type", 3))                  # 0x000B
        self.registers.append(SDM630Register(13, 7, "Pulse1 Width", "Milliseconds", 5.0))       # 0x000D
        self.registers.append(SDM630Register(15, 8, "Password Lock", "Boolean", 0.0))           # 0x000F
        self.registers.append(SDM630Register(19, 10, "Network Parity Stop", "Float", 1.0))      # 0x0013 One stop bit and even parity
        self.registers.append(SDM630Register(21, 11, "Network Node", "Float", 1.0))             # 0x0015
        self.registers.append(SDM630Register(23, 12, "Pulse1 Divisor1", "Float", 3.0))          # 0x0017
        self.registers.append(SDM630Register(25, 13, "Password", "Float", 0000))                # 0x0019
        self.registers.append(SDM630Register(29, 15, "Network Baud Rate", "Mode", 2.0))         # 0x001D
        self.registers.append(SDM630Register(87, 44, "Pulse 1 Energy Type", "Source", 4.0))     # 0x0057
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