"""
Common register object for SDM630 Modbus simulator
"""
from dataclasses import dataclass

@dataclass
class SDM630Register:
    address: int
    parameter_number: int
    description: str
    units: str
    value: float = 0.0
    example_value: float = 0.0
    negative_to_grid: bool = False  # True if negative values indicate power to grid

    def __init__(self, address, parameter_number, description, units, example_value=0.0, negative_to_grid=False):
        self.address = address
        self.parameter_number = parameter_number
        self.description = description
        self.units = units
        self.value = example_value
        self.example_value = example_value
        self.negative_to_grid = negative_to_grid

    def set_value(self, value):
        self.value = value

    def get_value(self):
        return self.value
    
    def get_address(self):
        return self.address

@dataclass
class SDM630Registers:
    registers: list[SDM630Register]

    def __init__(self, registers: list[SDM630Register] | None = None):
        self.registers = registers if registers is not None else []

    def get_all(self):
        return self.registers
    
    def set_float(self, address, value):
        """Set a float value in the register by address."""
        for reg in self.registers:
            if reg.address == address:
                reg.set_value(value)
                return
            
        raise ValueError(f"Register with address '{address}' not found.")
    
    def get_float(self, address):
        """Get a float value from the register by address."""
        for reg in self.registers:
            if reg.address == address:
                return reg.get_value()
            
        raise ValueError(f"Register with address '{address}' not found.")