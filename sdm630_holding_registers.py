"""
SDM630 Holding Register Definitions
All holding registers for SDM630, with metadata from specification.
"""
from registers import SDM630Register

class SDM630HoldingRegisters:
    def __init__(self):
        self.registers = []
        self._init_registers()

    def _init_registers(self):
        # Example subset, expand as needed from specification
        self.registers.append(SDM630Register(2, 2, "Demand Period", "Minutes", 60.0))
        self.registers.append(SDM630Register(10, 6, "System Type", "Type", 1.0))
        # ... add all other holding registers from specification here

    def get_by_address(self, address):
        for reg in self.registers:
            if reg.address == address:
                return reg
        return None

    def get_all(self):
        return self.registers

    def as_dict(self):
        return {reg.address: reg.get_value() for reg in self.registers}
