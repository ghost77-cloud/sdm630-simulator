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
        self._init_registers()

    def _init_registers(self):
        # Example subset, expand as needed from specification
        self.registers.append(SDM630Register(2, 2, "Demand Period", "Minutes", 60.0))
        self.registers.append(SDM630Register(10, 6, "System Type", "Type", 1.0))
        # ... add all other holding registers from specification here
        super().__init__(self.registers)

    def get_by_address(self, address):
        for reg in self.registers:
            if reg.address == address:
                return reg
        return None